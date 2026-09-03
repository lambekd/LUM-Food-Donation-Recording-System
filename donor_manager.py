"""
Donor management interface for viewing, adding, editing, and deleting donors.
"""
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional, List
from core.models import Donor
from core.storage import Storage


class DonorManagerFrame(ctk.CTkFrame):
    def __init__(self, master, storage: Storage, on_donors_changed: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.storage = storage
        self.on_donors_changed = on_donors_changed
        self.donors: List[Donor] = []

        self._build_ui()
        self.refresh_donors()

    def _build_ui(self):
        # Header / Controls Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            top_bar,
            text="Donor Management",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_lbl.pack(side="left")

        add_btn = ctk.CTkButton(
            top_bar,
            text="+ Add New Donor",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#28a745",
            hover_color="#218838",
            command=self._open_add_dialog
        )
        add_btn.pack(side="right", padx=(10, 0))

        # Search Bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search donors by name or category...",
            height=36
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_donors())

        clear_btn = ctk.CTkButton(
            search_frame,
            text="Clear",
            width=70,
            command=self._clear_search
        )
        clear_btn.pack(side="right")

        # Scrollable Donor List
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Registered Donors")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def refresh_donors(self):
        self.donors = self.storage.get_all_donors(active_only=False)
        self._filter_donors()

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self._filter_donors()

    def _filter_donors(self):
        query = self.search_entry.get().strip().lower()

        # Clear existing rows in scrollable frame
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        filtered = [
            d for d in self.donors
            if query in d.name.lower() or query in d.category.lower() or query in d.contact_info.lower()
        ]

        if not filtered:
            no_data_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="No donors found." if query else "No donors registered yet.",
                text_color="gray",
                font=ctk.CTkFont(size=14)
            )
            no_data_lbl.pack(pady=30)
            return

        for donor in filtered:
            self._render_donor_row(donor)

    def _render_donor_row(self, donor: Donor):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=("gray90", "gray18"), corner_radius=8)
        card.pack(fill="x", padx=5, pady=4)

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        name_lbl = ctk.CTkLabel(
            info_frame,
            text=donor.name,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w"
        )
        name_lbl.pack(anchor="w")

        sub_text = f"Category: {donor.category}"
        if donor.contact_info:
            sub_text += f"  |  Contact: {donor.contact_info}"
        
        details_lbl = ctk.CTkLabel(
            info_frame,
            text=sub_text,
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
            anchor="w"
        )
        details_lbl.pack(anchor="w", pady=(2, 0))

        # Actions
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.pack(side="right", padx=10)

        edit_btn = ctk.CTkButton(
            actions_frame,
            text="Edit",
            width=65,
            height=30,
            command=lambda d=donor: self._open_edit_dialog(d)
        )
        edit_btn.pack(side="left", padx=4)

        del_btn = ctk.CTkButton(
            actions_frame,
            text="Delete",
            width=65,
            height=30,
            fg_color="#dc3545",
            hover_color="#c82333",
            command=lambda d=donor: self._delete_donor(d)
        )
        del_btn.pack(side="left", padx=4)

    def _open_add_dialog(self):
        DonorDialog(self, title="Add New Donor", on_save=self._save_new_donor)

    def _open_edit_dialog(self, donor: Donor):
        DonorDialog(self, title="Edit Donor", donor=donor, on_save=self._save_existing_donor)

    def _save_new_donor(self, donor: Donor):
        try:
            self.storage.add_donor(donor)
            self.refresh_donors()
            if self.on_donors_changed:
                self.on_donors_changed()
        except Exception as e:
            messagebox.showerror("Error", f"Could not add donor: {e}")

    def _save_existing_donor(self, donor: Donor):
        try:
            self.storage.update_donor(donor)
            self.refresh_donors()
            if self.on_donors_changed:
                self.on_donors_changed()
        except Exception as e:
            messagebox.showerror("Error", f"Could not update donor: {e}")

    def _delete_donor(self, donor: Donor):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete donor '{donor.name}'?"):
            if donor.id is not None:
                self.storage.delete_donor(donor.id)
                self.refresh_donors()
                if self.on_donors_changed:
                    self.on_donors_changed()


class DonorDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, donor: Optional[Donor] = None, on_save: Optional[Callable[[Donor], None]] = None):
        super().__init__(master)
        self.title(title)
        self.geometry("450x380")
        self.resizable(False, False)
        self.donor = donor
        self.on_save = on_save

        self.transient(master)
        self.grab_set()

        self._build_form()

    def _build_form(self):
        pad_x = 25
        
        title_lbl = ctk.CTkLabel(self, text=self.title(), font=ctk.CTkFont(size=18, weight="bold"))
        title_lbl.pack(padx=pad_x, pady=(20, 15), anchor="w")

        # Name
        ctk.CTkLabel(self, text="Donor Name *", font=ctk.CTkFont(size=13, weight="bold")).pack(padx=pad_x, anchor="w")
        self.name_entry = ctk.CTkEntry(self, placeholder_text="e.g. Acme Supermarket, Local Bakery", height=35)
        self.name_entry.pack(padx=pad_x, pady=(2, 12), fill="x")
        if self.donor:
            self.name_entry.insert(0, self.donor.name)

        # Category
        ctk.CTkLabel(self, text="Category", font=ctk.CTkFont(size=13, weight="bold")).pack(padx=pad_x, anchor="w")
        self.category_entry = ctk.CTkComboBox(
            self,
            values=["Retailer", "Grocery", "Bakery", "Farm/Garden", "Restaurant", "Distributor", "Community Member", "General"],
            height=35
        )
        self.category_entry.pack(padx=pad_x, pady=(2, 12), fill="x")
        if self.donor:
            self.category_entry.set(self.donor.category)
        else:
            self.category_entry.set("Grocery")

        # Contact Info
        ctk.CTkLabel(self, text="Contact Info (Email/Phone)", font=ctk.CTkFont(size=13, weight="bold")).pack(padx=pad_x, anchor="w")
        self.contact_entry = ctk.CTkEntry(self, placeholder_text="e.g. manager@store.com or 555-0199", height=35)
        self.contact_entry.pack(padx=pad_x, pady=(2, 20), fill="x")
        if self.donor:
            self.contact_entry.insert(0, self.donor.contact_info)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=pad_x, pady=(0, 20), fill="x")

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray50", hover_color="gray40", command=self.destroy)
        cancel_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        save_btn = ctk.CTkButton(btn_frame, text="Save Donor", fg_color="#007bff", hover_color="#0069d9", command=self._submit)
        save_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

    def _submit(self):
        name = self.name_entry.get().strip()
        category = self.category_entry.get().strip() or "General"
        contact = self.contact_entry.get().strip()

        if not name:
            messagebox.showwarning("Validation Error", "Please enter a donor name.")
            return

        if self.donor:
            self.donor.name = name
            self.donor.category = category
            self.donor.contact_info = contact
            target_donor = self.donor
        else:
            target_donor = Donor(name=name, category=category, contact_info=contact)

        if self.on_save:
            self.on_save(target_donor)
        self.destroy()
