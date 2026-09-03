"""
Submission History view showing logged records, sync status, and CSV export.
"""
import os
import csv
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Optional, List
from core.models import WeighRecord
from core.storage import Storage
from core.sheets_sync import SheetsSyncManager


class HistoryViewFrame(ctk.CTkFrame):
    def __init__(self, master, storage: Storage, sheets_manager: SheetsSyncManager, **kwargs):
        super().__init__(master, **kwargs)
        self.storage = storage
        self.sheets_manager = sheets_manager
        self.records: List[WeighRecord] = []

        self._build_ui()
        self.refresh_records()

    def _build_ui(self):
        # Header / Action Toolbar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            top_bar,
            text="Transaction History & Sync Log",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_lbl.pack(side="left")

        # Action Buttons
        btn_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_frame.pack(side="right")

        self.sync_btn = ctk.CTkButton(
            btn_frame,
            text="Sync All to Sheets",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#007bff",
            hover_color="#0069d9",
            command=self._sync_pending
        )
        self.sync_btn.pack(side="left", padx=4)

        export_btn = ctk.CTkButton(
            btn_frame,
            text="Export CSV",
            font=ctk.CTkFont(size=13),
            fg_color="#17a2b8",
            hover_color="#138496",
            command=self._export_csv
        )
        export_btn.pack(side="left", padx=4)

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="Refresh",
            width=75,
            command=self.refresh_records
        )
        refresh_btn.pack(side="left", padx=4)

        # Filter Bar
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=15, pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Filter history by donor, product, operator, notes, or date...",
            height=36
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_records())

        self.status_filter = ctk.CTkSegmentedButton(
            filter_bar,
            values=["All", "Synced", "Pending"],
            command=lambda v: self._filter_records()
        )
        self.status_filter.set("All")
        self.status_filter.pack(side="right")

        # Scrollable Record Table
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Recorded Weigh-ins")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def refresh_records(self):
        self.records = self.storage.get_recent_records(limit=250)
        self._filter_records()

    def _filter_records(self):
        query = self.search_entry.get().strip().lower()
        filter_mode = self.status_filter.get()

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        filtered = []
        for r in self.records:
            # Status filter
            if filter_mode == "Synced" and not r.synced_to_sheets:
                continue
            if filter_mode == "Pending" and r.synced_to_sheets:
                continue

            # Text search filter
            if query:
                combined = f"{r.timestamp} {r.donor_name} {r.product_name} {r.weight} {r.unit} {r.operator} {r.notes}".lower()
                if query not in combined:
                    continue

            filtered.append(r)

        if not filtered:
            no_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="No matching records found." if query or filter_mode != "All" else "No records logged yet.",
                text_color="gray",
                font=ctk.CTkFont(size=14)
            )
            no_lbl.pack(pady=30)
            return

        for record in filtered:
            self._render_record_card(record)

    def _render_record_card(self, record: WeighRecord):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=("gray90", "gray18"), corner_radius=8)
        card.pack(fill="x", padx=5, pady=4)

        # Left: Main Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        title_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        title_frame.pack(fill="x", anchor="w")

        weight_badge = ctk.CTkLabel(
            title_frame,
            text=f"{record.weight:.2f} {record.unit.upper()}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#007bff"
        )
        weight_badge.pack(side="left", padx=(0, 10))

        product_lbl = ctk.CTkLabel(
            title_frame,
            text=f"{record.product_name}  •  Donor: {record.donor_name}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        product_lbl.pack(side="left")

        # Sub details
        sub_info = f"Logged: {record.timestamp}"
        if record.operator:
            sub_info += f"  |  Op: {record.operator}"
        if record.notes:
            sub_info += f"  |  Notes: {record.notes}"

        details_lbl = ctk.CTkLabel(
            info_frame,
            text=sub_info,
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
            anchor="w"
        )
        details_lbl.pack(anchor="w", pady=(3, 0))

        # Right: Sync Status & Delete Action
        right_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_frame.pack(side="right", padx=10)

        # Sync Badge
        if record.synced_to_sheets:
            status_text = "Synced"
            badge_color = "#28a745"
        else:
            status_text = "Pending Sync" if not record.sync_error else "Sync Error"
            badge_color = "#ffc107" if not record.sync_error else "#dc3545"

        status_lbl = ctk.CTkLabel(
            right_frame,
            text=status_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="black" if badge_color == "#ffc107" else "white",
            fg_color=badge_color,
            corner_radius=6,
            width=90,
            height=26
        )
        status_lbl.pack(side="left", padx=(0, 8))

        del_btn = ctk.CTkButton(
            right_frame,
            text="✕",
            width=30,
            height=26,
            fg_color="#6c757d",
            hover_color="#dc3545",
            command=lambda r=record: self._delete_record(r)
        )
        del_btn.pack(side="left")

    def _sync_pending(self):
        self.sync_btn.configure(state="disabled", text="Syncing...")

        def worker():
            s_count, f_count, msg = self.sheets_manager.sync_all_pending()
            self.after(0, lambda: self._on_sync_finished(s_count, f_count, msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sync_finished(self, success_cnt: int, fail_cnt: int, msg: str):
        self.sync_btn.configure(state="normal", text="Sync All to Sheets")
        self.refresh_records()
        if fail_cnt == 0 and success_cnt > 0:
            messagebox.showinfo("Sync Successful", msg)
        elif fail_cnt > 0:
            messagebox.showwarning("Sync Warning", f"{msg}\nCheck Google Sheets configuration in Settings.")
        else:
            messagebox.showinfo("Sync Status", msg)

    def _delete_record(self, record: WeighRecord):
        if messagebox.askyesno("Delete Record", f"Delete record '{record.product_name} - {record.weight} {record.unit}'?"):
            if record.id:
                self.storage.delete_record(record.id)
                self.refresh_records()

    def _export_csv(self):
        if not self.records:
            messagebox.showwarning("Export Warning", "No records to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files (*.csv)", "*.csv"), ("All Files (*.*)", "*.*")],
            title="Export Weigh Records to CSV"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Timestamp", "Donor", "Food Product", "Weight", "Unit", "Operator", "Notes", "SyncedToSheets", "SyncError"])
                for r in self.records:
                    writer.writerow([
                        r.id,
                        r.timestamp,
                        r.donor_name,
                        r.product_name,
                        r.weight,
                        r.unit,
                        r.operator,
                        r.notes,
                        1 if r.synced_to_sheets else 0,
                        r.sync_error
                    ])
            messagebox.showinfo("Export Successful", f"Exported {len(self.records)} records to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write CSV file: {e}")
