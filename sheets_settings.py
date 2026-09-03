"""
Google Sheets Integration Settings interface.
Supports Google Apps Script Webhook and Google Cloud Service Account (gspread).
"""
import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Optional, Callable
from core.models import SheetsConfig
from core.storage import Storage
from core.sheets_sync import SheetsSyncManager


class SheetsSettingsFrame(ctk.CTkFrame):
    def __init__(self, master, storage: Storage, sheets_manager: SheetsSyncManager, on_settings_saved: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.storage = storage
        self.sheets_manager = sheets_manager
        self.on_settings_saved = on_settings_saved
        self.config: SheetsConfig = storage.get_sheets_config()

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        # Header
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            top_bar,
            text="Google Sheets Integration",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left")

        # Scrollable settings area
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # --- Mode Selector ---
        mode_card = ctk.CTkFrame(scroll)
        mode_card.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(mode_card, text="Integration Method", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 6))

        self.mode_segment = ctk.CTkSegmentedButton(
            mode_card,
            values=["Google Apps Script Webhook", "Google Service Account", "Offline / Disabled"],
            command=self._on_mode_change
        )
        self.mode_segment.pack(fill="x", padx=15, pady=(0, 12))

        # --- Card 1: Webhook Settings ---
        self.webhook_card = ctk.CTkFrame(scroll)
        self.webhook_card.pack(fill="x", pady=8, padx=5)

        wh_header = ctk.CTkFrame(self.webhook_card, fg_color="transparent")
        wh_header.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(wh_header, text="Apps Script Webhook Setup (Recommended)", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        
        info_btn = ctk.CTkButton(
            wh_header,
            text="Setup Guide & Script Code",
            width=180,
            height=28,
            fg_color="#17a2b8",
            hover_color="#138496",
            command=self._show_apps_script_guide
        )
        info_btn.pack(side="right")

        ctk.CTkLabel(
            self.webhook_card,
            text="Paste your deployed Google Apps Script Web App URL below:",
            text_color=("gray40", "gray60"),
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=15, pady=(0, 6))

        self.webhook_entry = ctk.CTkEntry(
            self.webhook_card,
            placeholder_text="https://script.google.com/macros/s/.../exec",
            height=36
        )
        self.webhook_entry.pack(fill="x", padx=15, pady=(0, 15))

        # --- Card 2: Service Account Settings ---
        self.sa_card = ctk.CTkFrame(scroll)
        self.sa_card.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(self.sa_card, text="Google Cloud Service Account (gspread)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 6))

        # Credentials File
        ctk.CTkLabel(self.sa_card, text="Service Account JSON Credentials File:").pack(anchor="w", padx=15, pady=(4, 2))
        creds_row = ctk.CTkFrame(self.sa_card, fg_color="transparent")
        creds_row.pack(fill="x", padx=15, pady=(0, 10))

        self.creds_entry = ctk.CTkEntry(creds_row, placeholder_text="Path to credentials.json", height=36)
        self.creds_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(creds_row, text="Browse...", width=90, height=36, command=self._browse_credentials)
        browse_btn.pack(side="right")

        # Sheet Name / ID
        ctk.CTkLabel(self.sa_card, text="Google Sheet Name, ID, or Full URL:").pack(anchor="w", padx=15, pady=(4, 2))
        self.sheet_entry = ctk.CTkEntry(self.sa_card, placeholder_text="e.g. 'Food Bank Weigh Log' or full URL", height=36)
        self.sheet_entry.pack(fill="x", padx=15, pady=(0, 10))

        # Worksheet tab name
        ctk.CTkLabel(self.sa_card, text="Worksheet / Tab Name (default: 'Sheet1'):").pack(anchor="w", padx=15, pady=(4, 2))
        self.ws_entry = ctk.CTkEntry(self.sa_card, placeholder_text="Sheet1", height=36)
        self.ws_entry.pack(fill="x", padx=15, pady=(0, 15))

        # --- Options & Test Connection ---
        options_card = ctk.CTkFrame(scroll)
        options_card.pack(fill="x", pady=8, padx=5)

        self.auto_sync_switch = ctk.CTkSwitch(
            options_card,
            text="Automatically upload weigh records to Google Sheets immediately upon saving",
            font=ctk.CTkFont(size=13)
        )
        self.auto_sync_switch.pack(anchor="w", padx=15, pady=12)

        # Test Connection Action
        test_row = ctk.CTkFrame(options_card, fg_color="transparent")
        test_row.pack(fill="x", padx=15, pady=(0, 15))

        self.test_btn = ctk.CTkButton(
            test_row,
            text="⚡ Test Google Sheets Connection",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#17a2b8",
            hover_color="#138496",
            command=self._test_connection
        )
        self.test_btn.pack(side="left", padx=(0, 10))

        self.test_status_lbl = ctk.CTkLabel(test_row, text="Status: Ready", text_color="gray")
        self.test_status_lbl.pack(side="left")

        # Save Button Bar
        bottom_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        bottom_bar.pack(fill="x", pady=(15, 10))

        save_btn = ctk.CTkButton(
            bottom_bar,
            text="Save Google Sheets Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#007bff",
            hover_color="#0069d9",
            height=40,
            command=self._save_settings
        )
        save_btn.pack(side="right", padx=5)

    def _load_values(self):
        mode = self.config.auth_mode
        if mode == "webhook":
            self.mode_segment.set("Google Apps Script Webhook")
        elif mode == "service_account":
            self.mode_segment.set("Google Service Account")
        else:
            self.mode_segment.set("Offline / Disabled")

        self.webhook_entry.delete(0, "end")
        self.webhook_entry.insert(0, self.config.webhook_url)

        self.creds_entry.delete(0, "end")
        self.creds_entry.insert(0, self.config.credentials_file)

        self.sheet_entry.delete(0, "end")
        self.sheet_entry.insert(0, self.config.sheet_id_or_name)

        self.ws_entry.delete(0, "end")
        self.ws_entry.insert(0, self.config.worksheet_name)

        if self.config.auto_sync:
            self.auto_sync_switch.select()
        else:
            self.auto_sync_switch.deselect()

        self._update_card_visibility()

    def _on_mode_change(self, val):
        self._update_card_visibility()

    def _update_card_visibility(self):
        mode = self.mode_segment.get()
        if "Webhook" in mode:
            self.webhook_card.pack(fill="x", pady=8, padx=5)
            self.sa_card.pack_forget()
        elif "Service Account" in mode:
            self.webhook_card.pack_forget()
            self.sa_card.pack(fill="x", pady=8, padx=5)
        else:
            self.webhook_card.pack_forget()
            self.sa_card.pack_forget()

    def _browse_credentials(self):
        f = filedialog.askopenfilename(
            title="Select Google Service Account JSON File",
            filetypes=[("JSON Files (*.json)", "*.json"), ("All Files (*.*)", "*.*")]
        )
        if f:
            self.creds_entry.delete(0, "end")
            self.creds_entry.insert(0, f)

    def _build_config_from_ui(self) -> SheetsConfig:
        mode_val = self.mode_segment.get()
        if "Webhook" in mode_val:
            auth_mode = "webhook"
        elif "Service Account" in mode_val:
            auth_mode = "service_account"
        else:
            auth_mode = "disabled"

        return SheetsConfig(
            auth_mode=auth_mode,
            credentials_file=self.creds_entry.get().strip(),
            sheet_id_or_name=self.sheet_entry.get().strip(),
            worksheet_name=self.ws_entry.get().strip() or "Sheet1",
            webhook_url=self.webhook_entry.get().strip(),
            auto_sync=self.auto_sync_switch.get() == 1
        )

    def _test_connection(self):
        cfg = self._build_config_from_ui()
        self.sheets_manager.update_config(cfg)

        self.test_btn.configure(state="disabled", text="Testing...")
        self.test_status_lbl.configure(text="Connecting to Google Sheets...", text_color="#ffc107")

        def worker():
            success, msg = self.sheets_manager.test_connection()
            self.after(0, lambda: self._on_test_finished(success, msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_finished(self, success: bool, msg: str):
        self.test_btn.configure(state="normal", text="⚡ Test Google Sheets Connection")
        if success:
            self.test_status_lbl.configure(text=f"Success: {msg}", text_color="#28a745")
            messagebox.showinfo("Connection Test Passed", msg)
        else:
            self.test_status_lbl.configure(text="Test Failed", text_color="#dc3545")
            messagebox.showerror("Connection Test Failed", msg)

    def _save_settings(self):
        new_cfg = self._build_config_from_ui()
        self.storage.save_sheets_config(new_cfg)
        self.config = new_cfg
        self.sheets_manager.update_config(new_cfg)

        if self.on_settings_saved:
            self.on_settings_saved()

        messagebox.showinfo("Saved", "Google Sheets settings saved successfully!")

    def _show_apps_script_guide(self):
        guide_dialog = ctk.CTkToplevel(self)
        guide_dialog.title("Google Apps Script Setup Guide")
        guide_dialog.geometry("600x520")
        guide_dialog.transient(self)

        content = ctk.CTkScrollableFrame(guide_dialog)
        content.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            content,
            text="How to Connect with Google Apps Script (3 Minutes)",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        steps_text = (
            "1. Open your target Google Sheet in your web browser.\n"
            "2. In Google Sheets menu, click: Extensions -> Apps Script.\n"
            "3. Erase existing code and copy/paste the script below.\n"
            "4. Click Deploy (top right) -> New deployment.\n"
            "5. Select type: 'Web app'.\n"
            "6. Set 'Execute as': 'Me', and 'Who has access': 'Anyone'.\n"
            "7. Click Deploy, authorize permissions, and copy the Web App URL.\n"
            "8. Paste the Web App URL into the Scale App Settings!"
        )
        ctk.CTkLabel(content, text=steps_text, justify="left", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(content, text="Script Code (ready to copy):", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(5, 5))

        script_box = ctk.CTkTextbox(content, height=180, font=ctk.CTkFont(family="Consolas", size=11))
        script_box.pack(fill="x", pady=(0, 10))
        
        # Read script code from assets/google_apps_script.js
        script_code = ""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            as_path = os.path.join(base_dir, "assets", "google_apps_script.js")
            with open(as_path, "r", encoding="utf-8") as f:
                script_code = f.read()
        except Exception:
            script_code = "// See assets/google_apps_script.js"

        script_box.insert("1.0", script_code)

        close_btn = ctk.CTkButton(content, text="Close", command=guide_dialog.destroy)
        close_btn.pack(pady=5)
