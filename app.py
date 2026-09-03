"""
Scale to Google Sheets Desktop Application.
Main entry point and application container.
"""
import sys
import os
import customtkinter as ctk
from core.storage import Storage
from core.scale_reader import ScaleReader
from core.sheets_sync import SheetsSyncManager
from ui.main_view import MainWeighViewFrame
from ui.donor_manager import DonorManagerFrame
from ui.product_manager import ProductManagerFrame
from ui.history_view import HistoryViewFrame
from ui.scale_settings import ScaleSettingsFrame
from ui.sheets_settings import SheetsSettingsFrame


# Set CustomTkinter theme and appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ScaleApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("USB Scale to Google Sheets Logger")
        self.geometry("1100x740")
        self.minsize(960, 640)

        # Core engines
        self.storage = Storage()
        self.scale_reader = ScaleReader(self.storage.get_scale_config())
        self.sheets_manager = SheetsSyncManager(self.storage)

        # Start scale reader
        self.scale_reader.start()

        # Listen to sheets manager updates
        self.sheets_manager.add_status_listener(self._on_sheets_status_update)

        self._build_ui()
        self._update_status_bar()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # 1. Top Navbar / Header
        self.header_frame = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=("gray85", "gray13"))
        self.header_frame.pack(fill="x", side="top")

        # Brand / Title
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        app_title = ctk.CTkLabel(
            title_box,
            text="⚖ SCALE LOGGER",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#007bff", "#38bdf8")
        )
        app_title.pack(side="left")

        app_sub = ctk.CTkLabel(
            title_box,
            text="to Google Sheets",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray60")
        )
        app_sub.pack(side="left", padx=(8, 0))

        # Theme toggle (top right)
        theme_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        theme_box.pack(side="right", padx=15, pady=10)

        self.theme_switch = ctk.CTkSwitch(
            theme_box,
            text="Dark Mode",
            font=ctk.CTkFont(size=12),
            command=self._toggle_theme
        )
        self.theme_switch.select()
        self.theme_switch.pack()

        # 2. Main Tab View
        self.tabview = ctk.CTkTabview(self, corner_radius=10, fg_color=("gray90", "gray17"))
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(5, 5))

        # Add tabs
        self.tab_weigh = self.tabview.add("  Weigh Station  ")
        self.tab_history = self.tabview.add("  History & Sync  ")
        self.tab_donors = self.tabview.add("  Donors List  ")
        self.tab_products = self.tabview.add("  Food Products  ")
        self.tab_scale = self.tabview.add("  Scale / COM Port  ")
        self.tab_sheets = self.tabview.add("  Google Sheets Settings  ")

        # Tab 1: Main Weigh Station
        self.weigh_view = MainWeighViewFrame(
            self.tab_weigh,
            storage=self.storage,
            scale_reader=self.scale_reader,
            sheets_manager=self.sheets_manager,
            on_record_saved=self._on_record_saved
        )
        self.weigh_view.pack(fill="both", expand=True)

        # Tab 2: History & Sync
        self.history_view = HistoryViewFrame(
            self.tab_history,
            storage=self.storage,
            sheets_manager=self.sheets_manager
        )
        self.history_view.pack(fill="both", expand=True)

        # Tab 3: Donors
        self.donor_view = DonorManagerFrame(
            self.tab_donors,
            storage=self.storage,
            on_donors_changed=self._on_donors_changed
        )
        self.donor_view.pack(fill="both", expand=True)

        # Tab 4: Products
        self.product_view = ProductManagerFrame(
            self.tab_products,
            storage=self.storage,
            on_products_changed=self._on_products_changed
        )
        self.product_view.pack(fill="both", expand=True)

        # Tab 5: Scale Settings
        self.scale_settings_view = ScaleSettingsFrame(
            self.tab_scale,
            storage=self.storage,
            scale_reader=self.scale_reader,
            on_scale_reconnected=self._on_scale_reconnected
        )
        self.scale_settings_view.pack(fill="both", expand=True)

        # Tab 6: Sheets Settings
        self.sheets_settings_view = SheetsSettingsFrame(
            self.tab_sheets,
            storage=self.storage,
            sheets_manager=self.sheets_manager,
            on_settings_saved=self._on_sheets_settings_saved
        )
        self.sheets_settings_view.pack(fill="both", expand=True)

        # 3. Bottom Status Bar
        self.status_bar = ctk.CTkFrame(self, height=32, corner_radius=0, fg_color=("gray85", "gray12"))
        self.status_bar.pack(fill="x", side="bottom")

        self.scale_status_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Scale: Initializing...",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70")
        )
        self.scale_status_lbl.pack(side="left", padx=15, pady=4)

        self.sheets_status_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Sheets: Ready",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70")
        )
        self.sheets_status_lbl.pack(side="left", padx=15, pady=4)

        self.records_count_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Total Records: 0",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70")
        )
        self.records_count_lbl.pack(side="right", padx=15, pady=4)

    def _toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="Dark Mode")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="Light Mode")

    def _on_donors_changed(self):
        self.weigh_view.refresh_dropdowns()

    def _on_products_changed(self):
        self.weigh_view.refresh_dropdowns()

    def _on_scale_reconnected(self):
        self._update_status_bar()

    def _on_sheets_settings_saved(self):
        self._update_status_bar()

    def _on_record_saved(self, record):
        self.history_view.refresh_records()
        self._update_status_bar()

    def _on_sheets_status_update(self, msg: str, success: bool, record):
        try:
            if self.winfo_exists():
                self.after(0, lambda: self._handle_sheets_status(msg, success, record))
        except Exception:
            pass

    def _handle_sheets_status(self, msg: str, success: bool, record):
        if success:
            self.sheets_status_lbl.configure(text=f"Sheets: Synced ({msg})", text_color="#28a745")
        else:
            self.sheets_status_lbl.configure(text=f"Sheets: Sync Error ({msg})", text_color="#dc3545")
        self.history_view.refresh_records()

    def _update_status_bar(self):
        # Scale Status
        cfg = self.scale_reader.config
        if cfg.use_simulator or cfg.port.upper() == "SIMULATOR":
            self.scale_status_lbl.configure(text="Scale: Virtual Simulator (Active)", text_color="#17a2b8")
        elif self.scale_reader.is_connected:
            self.scale_status_lbl.configure(text=f"Scale: {cfg.port} @ {cfg.baudrate} baud (Connected)", text_color="#28a745")
        else:
            self.scale_status_lbl.configure(text=f"Scale: {cfg.port} (Disconnected / Scanning)", text_color="#ffc107")

        # Sheets Status
        s_cfg = self.storage.get_sheets_config()
        if s_cfg.auth_mode == "disabled":
            self.sheets_status_lbl.configure(text="Sheets: Offline (Local DB Only)", text_color="gray")
        elif s_cfg.auth_mode == "webhook":
            url_preview = s_cfg.webhook_url[:30] + "..." if len(s_cfg.webhook_url) > 30 else s_cfg.webhook_url
            self.sheets_status_lbl.configure(text=f"Sheets: Webhook ({url_preview or 'Not Configured'})", text_color="#007bff" if s_cfg.webhook_url else "gray")
        else:
            self.sheets_status_lbl.configure(text=f"Sheets: Service Account ({s_cfg.sheet_id_or_name or 'No Sheet'})", text_color="#007bff")

        # Records Count
        total = len(self.storage.get_recent_records(limit=1000))
        self.records_count_lbl.configure(text=f"Total Records: {total}")

    def _on_close(self):
        """Clean shutdown of background threads."""
        try:
            self.scale_reader.stop()
            self.sheets_manager.stop_worker()
        except Exception:
            pass
        self.destroy()


def main():
    app = ScaleApp()
    app.mainloop()


if __name__ == "__main__":
    main()
