"""
Primary Weigh & Log Form Dashboard.
Provides donor selection, food product selection, scale weight capture,
manual override, and instant one-click logging to Google Sheets.
"""
import time
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List, Callable
from core.models import Donor, FoodProduct, WeighRecord
from core.storage import Storage
from core.scale_reader import ScaleReader
from core.sheets_sync import SheetsSyncManager
from .donor_manager import DonorDialog
from .product_manager import ProductDialog


class MainWeighViewFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        storage: Storage,
        scale_reader: ScaleReader,
        sheets_manager: SheetsSyncManager,
        on_record_saved: Optional[Callable[[WeighRecord], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.storage = storage
        self.scale_reader = scale_reader
        self.sheets_manager = sheets_manager
        self.on_record_saved = on_record_saved

        self.donors: List[Donor] = []
        self.products: List[FoodProduct] = []

        self.current_weight: float = 0.0
        self.current_unit: str = "lbs"
        self.is_manual_entry: bool = False
        self.tare_offset: float = 0.0

        self._build_ui()
        self.refresh_dropdowns()

        # Register scale listener
        self.scale_reader.add_listener(self._on_scale_update)

    def _build_ui(self):
        # 2-Column Responsive Layout
        self.columnconfigure(0, weight=6)  # Left column (Form & Scale)
        self.columnconfigure(1, weight=4)  # Right column (Status & Recent Activity)
        self.rowconfigure(0, weight=1)

        # Left Column Frame
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)

        # Right Column Frame
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)

        # ==========================================
        # LEFT COLUMN: PRIMARY WEIGH & LOG WORKFLOW
        # ==========================================

        # --- Card 1: Scale Readout & Actions ---
        scale_card = ctk.CTkFrame(left_frame, corner_radius=12)
        scale_card.pack(fill="x", pady=(0, 15))

        scale_header = ctk.CTkFrame(scale_card, fg_color="transparent")
        scale_header.pack(fill="x", padx=15, pady=(12, 5))

        ctk.CTkLabel(
            scale_header,
            text="SCALE WEIGHT READOUT",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("gray40", "gray60")
        ).pack(side="left")

        self.scale_status_badge = ctk.CTkLabel(
            scale_header,
            text="Scale: Initializing",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#6c757d",
            text_color="white",
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.scale_status_badge.pack(side="right")

        # Digital LCD Display Box
        display_box = ctk.CTkFrame(scale_card, fg_color=("gray95", "gray10"), corner_radius=10)
        display_box.pack(fill="x", padx=15, pady=8)

        self.weight_label = ctk.CTkLabel(
            display_box,
            text="0.00",
            font=ctk.CTkFont(size=56, weight="bold"),
            text_color=("#007bff", "#38bdf8")
        )
        self.weight_label.pack(side="left", padx=(25, 10), pady=15)

        unit_frame = ctk.CTkFrame(display_box, fg_color="transparent")
        unit_frame.pack(side="left", pady=15)

        self.unit_label = ctk.CTkLabel(
            unit_frame,
            text="LBS",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=("gray30", "gray70")
        )
        self.unit_label.pack(anchor="w")

        self.stability_label = ctk.CTkLabel(
            unit_frame,
            text="[STABLE]",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#28a745"
        )
        self.stability_label.pack(anchor="w")

        # Scale Control Buttons
        scale_btn_row = ctk.CTkFrame(scale_card, fg_color="transparent")
        scale_btn_row.pack(fill="x", padx=15, pady=(5, 15))

        self.read_btn = ctk.CTkButton(
            scale_btn_row,
            text="📥 Read Scale Weight",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=46,
            fg_color="#007bff",
            hover_color="#0069d9",
            command=self._fetch_scale_weight
        )
        self.read_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.tare_btn = ctk.CTkButton(
            scale_btn_row,
            text="Zero / Tare",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=46,
            width=100,
            fg_color="gray50",
            hover_color="gray40",
            command=self._tare_scale
        )
        self.tare_btn.pack(side="left", padx=(0, 8))

        self.manual_toggle_btn = ctk.CTkButton(
            scale_btn_row,
            text="Manual Entry",
            font=ctk.CTkFont(size=13),
            height=46,
            width=110,
            fg_color="transparent",
            border_width=1,
            border_color=("gray60", "gray40"),
            command=self._toggle_manual_entry
        )
        self.manual_toggle_btn.pack(side="right")

        # Manual Entry Input Container (Hidden by default)
        self.manual_frame = ctk.CTkFrame(scale_card, fg_color="transparent")
        ctk.CTkLabel(self.manual_frame, text="Manual Weight Value:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(15, 8))
        self.manual_entry = ctk.CTkEntry(self.manual_frame, placeholder_text="e.g. 12.50", width=120, height=34)
        self.manual_entry.pack(side="left", padx=(0, 10))
        self.manual_entry.bind("<KeyRelease>", lambda e: self._on_manual_text_change())
        self.manual_unit_seg = ctk.CTkSegmentedButton(self.manual_frame, values=["lbs", "kg", "oz", "g"], command=self._on_unit_change)
        self.manual_unit_seg.set("lbs")
        self.manual_unit_seg.pack(side="left")

        # --- Card 2: Transaction Form Fields ---
        form_card = ctk.CTkFrame(left_frame, corner_radius=12)
        form_card.pack(fill="both", expand=True)

        ctk.CTkLabel(
            form_card,
            text="TRANSACTION DETAILS",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", padx=15, pady=(12, 10))

        # Field 1: Donor Selector
        donor_label_row = ctk.CTkFrame(form_card, fg_color="transparent")
        donor_label_row.pack(fill="x", padx=15, pady=(0, 2))
        ctk.CTkLabel(donor_label_row, text="1. Select Donor *", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(
            donor_label_row,
            text="+ Add New Donor",
            width=110,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=("#007bff", "#38bdf8"),
            hover=False,
            command=self._quick_add_donor
        ).pack(side="right")

        self.donor_combobox = ctk.CTkComboBox(form_card, height=38, font=ctk.CTkFont(size=14))
        self.donor_combobox.pack(fill="x", padx=15, pady=(0, 12))

        # Field 2: Food Product Selector
        product_label_row = ctk.CTkFrame(form_card, fg_color="transparent")
        product_label_row.pack(fill="x", padx=15, pady=(0, 2))
        ctk.CTkLabel(product_label_row, text="2. Select Food Product *", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(
            product_label_row,
            text="+ Add New Product",
            width=120,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=("#007bff", "#38bdf8"),
            hover=False,
            command=self._quick_add_product
        ).pack(side="right")

        self.product_combobox = ctk.CTkComboBox(form_card, height=38, font=ctk.CTkFont(size=14), command=self._on_product_selected)
        self.product_combobox.pack(fill="x", padx=15, pady=(0, 12))

        # Field 3: Operator & Optional Notes
        meta_grid = ctk.CTkFrame(form_card, fg_color="transparent")
        meta_grid.pack(fill="x", padx=15, pady=(0, 12))
        meta_grid.columnconfigure(0, weight=1)
        meta_grid.columnconfigure(1, weight=1)

        ctk.CTkLabel(meta_grid, text="Operator / Staff Name:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.operator_entry = ctk.CTkEntry(meta_grid, placeholder_text="e.g. Volunteer 1", height=34)
        self.operator_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.operator_entry.insert(0, self.storage.get_general_settings().get("operator_name", "Operator 1"))

        ctk.CTkLabel(meta_grid, text="Notes / Batch # (Optional):", font=ctk.CTkFont(size=12)).grid(row=0, column=1, sticky="w", pady=(0, 2))
        self.notes_entry = ctk.CTkEntry(meta_grid, placeholder_text="e.g. Pallet #3, Exp 12/26", height=34)
        self.notes_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        # Big Submit Button
        self.submit_btn = ctk.CTkButton(
            form_card,
            text="✔ Save & Log to Google Sheet",
            font=ctk.CTkFont(size=17, weight="bold"),
            height=50,
            fg_color="#28a745",
            hover_color="#218838",
            command=self._submit_transaction
        )
        self.submit_btn.pack(fill="x", padx=15, pady=(10, 15))

        # Notification Banner
        self.banner = ctk.CTkLabel(
            form_card,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=30,
            corner_radius=6
        )

        # ==========================================
        # RIGHT COLUMN: LIVE STATS & RECENT LOGS
        # ==========================================

        # Stats Card
        stats_card = ctk.CTkFrame(right_frame, corner_radius=12)
        stats_card.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            stats_card,
            text="SESSION SUMMARY",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", padx=15, pady=(12, 10))

        stats_row = ctk.CTkFrame(stats_card, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=(0, 15))

        # Stat 1: Total Weight
        s1 = ctk.CTkFrame(stats_row, fg_color=("gray95", "gray14"), corner_radius=8)
        s1.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=4)
        self.total_weight_lbl = ctk.CTkLabel(s1, text="0.0 lbs", font=ctk.CTkFont(size=22, weight="bold"), text_color="#007bff")
        self.total_weight_lbl.pack(pady=(10, 2))
        ctk.CTkLabel(s1, text="Total Weighed", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 10))

        # Stat 2: Total Items
        s2 = ctk.CTkFrame(stats_row, fg_color=("gray95", "gray14"), corner_radius=8)
        s2.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        self.total_count_lbl = ctk.CTkLabel(s2, text="0", font=ctk.CTkFont(size=22, weight="bold"), text_color="#28a745")
        self.total_count_lbl.pack(pady=(10, 2))
        ctk.CTkLabel(s2, text="Entries Logged", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 10))

        # Quick History Card
        history_card = ctk.CTkFrame(right_frame, corner_radius=12)
        history_card.pack(fill="both", expand=True)

        ctk.CTkLabel(
            history_card,
            text="RECENT ACTIVITY",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", padx=15, pady=(12, 8))

        self.recent_scroll = ctk.CTkScrollableFrame(history_card)
        self.recent_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self.refresh_recent_activity()

    def refresh_dropdowns(self):
        """Refreshes Donor and Food Product dropdown options."""
        self.donors = self.storage.get_all_donors(active_only=True)
        donor_names = [d.name for d in self.donors]
        self.donor_combobox.configure(values=donor_names or ["No donors available"])
        if donor_names:
            if not self.donor_combobox.get() or self.donor_combobox.get() not in donor_names:
                self.donor_combobox.set(donor_names[0])

        self.products = self.storage.get_all_products(active_only=True)
        product_names = [p.name for p in self.products]
        self.product_combobox.configure(values=product_names or ["No products available"])
        if product_names:
            if not self.product_combobox.get() or self.product_combobox.get() not in product_names:
                self.product_combobox.set(product_names[0])

    def refresh_recent_activity(self):
        """Updates the recent activity feed in the right sidebar."""
        for w in self.recent_scroll.winfo_children():
            w.destroy()

        records = self.storage.get_recent_records(limit=10)
        total_wt = sum(r.weight for r in records)
        self.total_weight_lbl.configure(text=f"{total_wt:.1f} lbs")
        self.total_count_lbl.configure(text=str(len(records)))

        if not records:
            ctk.CTkLabel(self.recent_scroll, text="No entries yet today.", text_color="gray").pack(pady=20)
            return

        for r in records:
            item = ctk.CTkFrame(self.recent_scroll, fg_color=("gray95", "gray14"), corner_radius=6)
            item.pack(fill="x", pady=3)

            top = ctk.CTkFrame(item, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))

            ctk.CTkLabel(
                top,
                text=f"{r.weight:.2f} {r.unit}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#007bff"
            ).pack(side="left")

            status_color = "#28a745" if r.synced_to_sheets else "#ffc107"
            ctk.CTkLabel(
                top,
                text="Synced" if r.synced_to_sheets else "Pending",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=status_color
            ).pack(side="right")

            sub_txt = f"{r.product_name} • {r.donor_name}"
            ctk.CTkLabel(
                item,
                text=sub_txt,
                font=ctk.CTkFont(size=11),
                text_color=("gray40", "gray60"),
                anchor="w"
            ).pack(fill="x", padx=8, pady=(0, 6))

    def _on_product_selected(self, choice):
        # Auto set default unit from selected product
        for p in self.products:
            if p.name == choice:
                self.current_unit = p.default_unit
                self.unit_label.configure(text=self.current_unit.upper())
                self.manual_unit_seg.set(self.current_unit)
                break

    def _on_scale_update(self, weight: float, unit: str, is_stable: bool, raw: str):
        """Called automatically when scale sends new reading."""
        if self.is_manual_entry:
            return  # Ignore live scale if manual override is on

        net_weight = max(0.0, weight - self.tare_offset)
        self.current_weight = net_weight
        self.current_unit = unit

        # Update UI in main thread safely
        try:
            if self.winfo_exists():
                self.after(0, lambda: self._update_display(net_weight, unit, is_stable))
        except Exception:
            pass

    def _update_display(self, weight: float, unit: str, is_stable: bool):
        self.weight_label.configure(text=f"{weight:.2f}")
        self.unit_label.configure(text=unit.upper())
        if is_stable:
            self.stability_label.configure(text="[STABLE]", text_color="#28a745")
        else:
            self.stability_label.configure(text="[READING...]", text_color="#ffc107")

        # Update status badge
        if self.scale_reader.config.use_simulator or self.scale_reader.config.port.upper() == "SIMULATOR":
            self.scale_status_badge.configure(text="Simulator Mode", fg_color="#17a2b8")
        elif self.scale_reader.is_connected:
            self.scale_status_badge.configure(text=f"Scale: {self.scale_reader.config.port}", fg_color="#28a745")
        else:
            self.scale_status_badge.configure(text="Scale: Disconnected", fg_color="#dc3545")

    def _fetch_scale_weight(self):
        """Actively reads from scale on button push."""
        val, unit, stable, raw = self.scale_reader.read_weight_once()
        if val is not None:
            net = max(0.0, val - self.tare_offset)
            self.current_weight = net
            self.current_unit = unit
            self._update_display(net, unit, stable)
            self._show_banner(f"Scale reading captured: {net:.2f} {unit.upper()}", is_success=True)
        else:
            self._show_banner("Could not read scale. Check COM port or enable Simulator.", is_success=False)

    def _tare_scale(self):
        self.tare_offset = self.current_weight + self.tare_offset
        self.current_weight = 0.0
        self._update_display(0.0, self.current_unit, True)
        self._show_banner("Scale Zeroed / Tared", is_success=True)

    def _toggle_manual_entry(self):
        self.is_manual_entry = not self.is_manual_entry
        if self.is_manual_entry:
            self.manual_frame.pack(fill="x", padx=15, pady=(0, 12))
            self.manual_toggle_btn.configure(text="Auto Scale", fg_color="#17a2b8", text_color="white")
            self.manual_entry.focus()
            self._on_manual_text_change()
        else:
            self.manual_frame.pack_forget()
            self.manual_toggle_btn.configure(text="Manual Entry", fg_color="transparent", text_color=("black", "white"))

    def _on_manual_text_change(self):
        try:
            txt = self.manual_entry.get().strip()
            if txt:
                val = float(txt)
                self.current_weight = val
                self.weight_label.configure(text=f"{val:.2f}")
                self.stability_label.configure(text="[MANUAL ENTRY]", text_color="#17a2b8")
        except ValueError:
            pass

    def _on_unit_change(self, val):
        self.current_unit = val
        self.unit_label.configure(text=val.upper())

    def _quick_add_donor(self):
        DonorDialog(self, title="Add New Donor", on_save=self._save_quick_donor)

    def _save_quick_donor(self, donor: Donor):
        self.storage.add_donor(donor)
        self.refresh_dropdowns()
        self.donor_combobox.set(donor.name)

    def _quick_add_product(self):
        ProductDialog(self, title="Add Food Product", on_save=self._save_quick_product)

    def _save_quick_product(self, prod: FoodProduct):
        self.storage.add_product(prod)
        self.refresh_dropdowns()
        self.product_combobox.set(prod.name)
        self._on_product_selected(prod.name)

    def _submit_transaction(self):
        donor = self.donor_combobox.get().strip()
        product = self.product_combobox.get().strip()
        weight = self.current_weight
        unit = self.current_unit
        operator = self.operator_entry.get().strip()
        notes = self.notes_entry.get().strip()

        if not donor or donor == "No donors available":
            messagebox.showwarning("Incomplete Form", "Please select or add a Donor.")
            return

        if not product or product == "No products available":
            messagebox.showwarning("Incomplete Form", "Please select or add a Food Product.")
            return

        if weight <= 0.0:
            res = messagebox.askyesno(
                "Zero Weight Warning",
                "The current scale weight is 0.00. Are you sure you want to log a zero-weight record?"
            )
            if not res:
                return

        # Save operator name to settings
        if operator:
            self.storage.save_general_settings({"operator_name": operator})

        # Create Record
        record = WeighRecord(
            donor_name=donor,
            product_name=product,
            weight=round(weight, 2),
            unit=unit,
            notes=notes,
            operator=operator
        )

        # Store in local SQLite DB
        rec_id = self.storage.add_record(record)

        # Send to Google Sheets sync queue
        self.sheets_manager.enqueue_record(record)

        # Instant visual feedback
        msg = f"Saved: {weight:.2f} {unit} of {product} from {donor}"
        self._show_banner(msg, is_success=True)

        # Reset Form for next entry
        self.notes_entry.delete(0, "end")
        if self.is_manual_entry:
            self.manual_entry.delete(0, "end")

        # Refresh stats & parent
        self.refresh_recent_activity()
        if self.on_record_saved:
            self.on_record_saved(record)

    def _show_banner(self, text: str, is_success: bool = True):
        color = "#28a745" if is_success else "#dc3545"
        self.banner.configure(text=text, fg_color=color, text_color="white")
        self.banner.pack(fill="x", padx=15, pady=(0, 10))
        # Hide banner after 4 seconds
        self.after(4000, lambda: self.banner.pack_forget())
