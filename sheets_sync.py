"""
Google Sheets Sync module.
Handles synchronization of weigh records to Google Sheets via:
1. Google Cloud Service Account (gspread)
2. Google Apps Script Webhook (requests)
Includes background queue processing and offline resilience.
"""
import os
import json
import queue
import threading
from typing import Tuple, Optional, Callable, List
import requests
from .models import WeighRecord, SheetsConfig
from .storage import Storage


SHEET_HEADERS = [
    "Timestamp",
    "Donor",
    "Food Product",
    "Weight",
    "Unit",
    "Operator",
    "Notes"
]


class SheetsSyncManager:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.config: SheetsConfig = storage.get_sheets_config()
        self._sync_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._gspread_client = None
        self._status_listeners: List[Callable[[str, bool, Optional[WeighRecord]], None]] = []
        
        self.start_worker()

    def add_status_listener(self, cb: Callable[[str, bool, Optional[WeighRecord]], None]):
        if cb not in self._status_listeners:
            self._status_listeners.append(cb)

    def remove_status_listener(self, cb: Callable[[str, bool, Optional[WeighRecord]], None]):
        if cb in self._status_listeners:
            self._status_listeners.remove(cb)

    def _notify_status(self, message: str, is_success: bool, record: Optional[WeighRecord] = None):
        for cb in self._status_listeners:
            try:
                cb(message, is_success, record)
            except Exception as e:
                print(f"Error in sheets status listener: {e}")

    def update_config(self, new_config: SheetsConfig):
        self.config = new_config
        self._gspread_client = None  # Reset client cache

    def start_worker(self):
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self._worker_thread.start()

    def stop_worker(self):
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._sync_queue.put(None)
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

    def enqueue_record(self, record: WeighRecord):
        """Enqueues a record for background synchronization."""
        if not self.config.auto_sync or self.config.auth_mode == "disabled":
            return
        self._sync_queue.put(record)

    def _queue_worker(self):
        while self._running:
            try:
                record = self._sync_queue.get(timeout=1.0)
                if record is None:
                    break
                
                success, msg = self.sync_single_record(record)
                if record.id is not None:
                    self.storage.mark_record_synced(record.id, synced=success, error="" if success else msg)
                    record.synced_to_sheets = success
                    record.sync_error = "" if success else msg
                
                self._notify_status(msg, success, record)
                self._sync_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in sheets queue worker: {e}")

    def sync_single_record(self, record: WeighRecord) -> Tuple[bool, str]:
        """Synchronously uploads a single weigh record."""
        if self.config.auth_mode == "disabled":
            return True, "Sync is disabled in settings"

        if self.config.auth_mode == "webhook":
            return self._sync_via_webhook([record])
        elif self.config.auth_mode == "service_account":
            return self._sync_via_service_account([record])
        else:
            return False, f"Unknown auth mode: {self.config.auth_mode}"

    def sync_all_pending(self) -> Tuple[int, int, str]:
        """
        Synchronizes all unsynced records from the local database.
        Returns (success_count, fail_count, summary_message).
        """
        unsynced = self.storage.get_unsynced_records()
        if not unsynced:
            return 0, 0, "No pending records to sync"

        if self.config.auth_mode == "disabled":
            return 0, len(unsynced), "Google Sheets sync is disabled"

        if self.config.auth_mode == "webhook":
            success, msg = self._sync_via_webhook(unsynced)
            if success:
                for r in unsynced:
                    if r.id:
                        self.storage.mark_record_synced(r.id, True, "")
                return len(unsynced), 0, f"Successfully synced {len(unsynced)} records via Webhook"
            else:
                for r in unsynced:
                    if r.id:
                        self.storage.mark_record_synced(r.id, False, msg)
                return 0, len(unsynced), f"Webhook sync failed: {msg}"

        elif self.config.auth_mode == "service_account":
            success, msg = self._sync_via_service_account(unsynced)
            if success:
                for r in unsynced:
                    if r.id:
                        self.storage.mark_record_synced(r.id, True, "")
                return len(unsynced), 0, f"Successfully synced {len(unsynced)} records to Google Sheet"
            else:
                for r in unsynced:
                    if r.id:
                        self.storage.mark_record_synced(r.id, False, msg)
                return 0, len(unsynced), f"Service account sync failed: {msg}"

        return 0, len(unsynced), "Unknown sync configuration"

    # --- Webhook Implementation ---

    def _sync_via_webhook(self, records: List[WeighRecord]) -> Tuple[bool, str]:
        url = self.config.webhook_url.strip()
        if not url:
            return False, "Google Apps Script Webhook URL is empty"

        payload = [r.to_dict() for r in records]
        if len(payload) == 1:
            payload = payload[0]

        try:
            resp = requests.post(url, json=payload, timeout=12.0)
            if resp.status_code == 200:
                try:
                    res_json = resp.json()
                    if res_json.get("status") == "success" or res_json.get("status") == "ok":
                        return True, res_json.get("message", "Synced via Webhook")
                    elif "message" in res_json:
                        return True, res_json["message"]
                except Exception:
                    pass
                return True, "Data sent successfully (HTTP 200)"
            elif resp.status_code == 302:
                # Follow redirect (Google Apps script 302 redirect is normal)
                redirect_url = resp.headers.get("Location")
                if redirect_url:
                    r2 = requests.get(redirect_url, timeout=10.0)
                    return True, "Data sent successfully (HTTP Redirect handled)"
                return True, "Data sent successfully"
            else:
                return False, f"Server returned HTTP {resp.status_code}: {resp.text[:100]}"
        except requests.exceptions.RequestException as e:
            return False, f"Network error: {str(e)}"

    # --- Service Account Implementation ---

    def _get_gspread_client(self):
        if self._gspread_client is not None:
            return self._gspread_client

        import gspread
        from google.oauth2.service_account import Credentials

        creds_path = self.config.credentials_file.strip()
        if not creds_path or not os.path.exists(creds_path):
            raise FileNotFoundError(f"Credentials JSON file not found at: '{creds_path}'")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(credentials)
        self._gspread_client = client
        return client

    def _sync_via_service_account(self, records: List[WeighRecord]) -> Tuple[bool, str]:
        try:
            client = self._get_gspread_client()
            target = self.config.sheet_id_or_name.strip()
            if not target:
                return False, "Google Sheet Name or ID/URL is empty"

            # Open spreadsheet by URL, key, or title
            if "docs.google.com" in target:
                spreadsheet = client.open_by_url(target)
            elif len(target) > 30 and "/" not in target and " " not in target:
                try:
                    spreadsheet = client.open_by_key(target)
                except Exception:
                    spreadsheet = client.open(target)
            else:
                spreadsheet = client.open(target)

            # Get or create worksheet
            ws_name = self.config.worksheet_name.strip() or "Sheet1"
            try:
                worksheet = spreadsheet.worksheet(ws_name)
            except Exception:
                worksheet = spreadsheet.add_worksheet(title=ws_name, rows=1000, cols=10)

            # Check if headers exist; if sheet is empty, add headers
            try:
                first_row = worksheet.row_values(1)
                if not first_row:
                    worksheet.append_row(SHEET_HEADERS)
            except Exception:
                pass

            # Append all rows
            rows_to_add = [r.to_sheet_row() for r in records]
            worksheet.append_rows(rows_to_add)
            return True, f"Appended {len(rows_to_add)} row(s) to '{ws_name}'"

        except Exception as e:
            self._gspread_client = None  # Reset client cache on error
            return False, f"Google Sheet Error: {str(e)}"

    # --- Connection Testing ---

    def test_connection(self) -> Tuple[bool, str]:
        """Tests the configured connection."""
        if self.config.auth_mode == "disabled":
            return True, "Sync is currently set to Offline / Disabled"

        if self.config.auth_mode == "webhook":
            url = self.config.webhook_url.strip()
            if not url:
                return False, "Please provide a Webhook URL"
            try:
                resp = requests.get(url, timeout=8.0)
                if resp.status_code == 200 or resp.status_code == 302:
                    return True, "Webhook connection successful! (HTTP 200 OK)"
                return False, f"Webhook test failed with HTTP status {resp.status_code}"
            except Exception as e:
                return False, f"Webhook unreachable: {str(e)}"

        elif self.config.auth_mode == "service_account":
            creds_path = self.config.credentials_file.strip()
            if not creds_path or not os.path.exists(creds_path):
                return False, f"Credentials file '{creds_path}' does not exist"
            try:
                client = self._get_gspread_client()
                target = self.config.sheet_id_or_name.strip()
                if not target:
                    return False, "Please specify a Sheet Name or ID"
                if "docs.google.com" in target:
                    ss = client.open_by_url(target)
                elif len(target) > 30 and "/" not in target and " " not in target:
                    try:
                        ss = client.open_by_key(target)
                    except Exception:
                        ss = client.open(target)
                else:
                    ss = client.open(target)
                return True, f"Successfully connected to Google Sheet: '{ss.title}'"
            except Exception as e:
                self._gspread_client = None
                return False, f"Connection failed: {str(e)}"

        return False, "Invalid auth mode"
