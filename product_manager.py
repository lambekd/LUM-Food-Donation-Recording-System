"""
Food product management interface for viewing, adding, editing, and deleting food items.
"""
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional, List
from core.models import FoodProduct
from core.storage import Storage


class ProductManagerFrame(ctk.CTkFrame):
    def __init__(self, master, storage: Storage, on_products_changed: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.storage = storage
        self.on_products_changed = on_products_changed
        self.products: List[FoodProduct] = []

        self._build_ui()
        self.refresh_products()

    def _build_ui(self):
        # Header / Controls Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            top_bar,
            text="Food Products Management",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_lbl.pack(side="left")

        add_btn = ctk.CTkButton(
            top_bar,
            text="+ Add New Product",
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
            placeholder_text="Search food items by name, category, or unit...",
            height=36
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_products())

        clear_btn = ctk.CTkButton(
            search_frame,
            text="Clear",
            width=70,
            command=self._clear_search
        )
        clear_btn.pack(side="right")

        # Scrollable Product List
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Catalog of Food Products")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def refresh_products(self):
        self.products = self.storage.get_all_products(active_only=False)
        self._filter_products()

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self._filter_products()

    def _filter_products(self):
        query = self.search_entry.get().strip().lower()

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        filtered = [
            p for p in self.products
            if query in p.name.lower() or query in p.category.lower() or query in p.default_unit.lower()
        ]

        if not filtered:
            no_data_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="No food products found." if query else "No products registered yet.",
                text_color="gray",
                font=ctk.CTkFont(size=14)
            )
            no_data_lbl.pack(pady=30)
            return

        for prod in filtered:
            self._render_product_row(prod)

    def _render_product_row(self, prod: FoodProduct):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=("gray90", "gray18"), corner_radius=8)
        card.pack(fill="x", padx=5, pady=4)

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        name_lbl = ctk.CTkLabel(
            info_frame,
            text=prod.name,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w"
        )
        name_lbl.pack(anchor="w")

        details_lbl = ctk.CTkLabel(
            info_frame,
            text=f"Category: {prod.category}   |   Default Unit: {prod.default_unit.upper()}",
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
            command=lambda p=prod: self._open_edit_dialog(p)
        )
        edit_btn.pack(side="left", padx=4)

        del_btn = ctk.CTkButton(
            actions_frame,
            text="Delete",
            width=65,
            height=30,
            fg_color="#dc3545",
            hover_color="#c82333",
            command=lambda p=prod: self._delete_product(p)
        )
        del_btn.pack(side="left", padx=4)

    def _open_add_dialog(self):
        ProductDialog(self, title="Add Food Product", on_save=self._save_new_product)

    def _open_edit_dialog(self, prod: FoodProduct):
        ProductDialog(self, title="Edit Food Product", product=prod, on_save=self._save_existing_product)

    def _save_new_product(self, prod: FoodProduct):
        try:
            self.storage.add_product(prod)
            self.refresh_products()
            if self.on_products_changed:
                self.on_products_changed()
        except Exception as e:
            messagebox.showerror("Error", f"Could not add product: {e}")

    def _save_existing_product(self, prod: FoodProduct):
        try:
            self.storage.update_product(prod)
            self.refresh_products()
            if self.on_products_changed:
                self.on_products_changed()
        except Exception as e:
            messagebox.showerror("Error", f"Could not update product: {e}")

    def _delete_product(self, prod: FoodProduct):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete product '{prod.name}'?"):
            if prod.id is not None:
                self.storage.delete_product(prod.id)
                self.refresh_products()
                if self.on_products_changed:
                    self.on_products_changed()


class ProductDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, product: Optional[FoodProduct] = None, on_save: Optional[Callable[[FoodProduct], None]] = None):
        super().__init__(master)
        self.title(title)
        self.geometry("450x380")
        self.resizable(False, False)
        self.product = product
        self.on_save = on_save

        self.transient(master)
        self.grab_set()

        self._build_form()

    def _build_form(self):
        pad_x = 25

        title_lbl = ctk.CTkLabel(self, text=self.title(), font=ctk.CTkFont(size=18, weight="bold"))
        title_lbl.pack(padx=pad_x, pady=(20, 15), anchor="w")

        # Name
        ctk.CTkLabel(self, text="Product Name *", font=ctk.CTkFont(size=13, weight="bold")).pack(padx=pad_x, anchor="w")
        self.name_entry = ctk.CTkEntry(self, placeholder_text="e.g. Fresh Apples, Canned Beans, Bread", height=35)
        self.name_entry.pack(padx=pad_x, pady=(2, 12), fill="x")
        if self.product:
            self.name_entry.insert(0, self.product.name)

        # Category
        ctk.CTkLabel(self, text="Category", font=ctk.CTkFont(size=13, weight="bold")).pack(padx=pad_x, anchor="w")
        self.category_entry = ctk.CTkComboBox(
            self,
            values=["Produce", "Canned Goods", "Dry Goods", "Bakery", "Dairy", "Meat/Protein", "Frozen", "Beverages", "Prepared Meals", "General"],
            height=35
        )
        self.category_entry.pack(padx=pad_x, pady=(2, 12), fill="x")
        if self.product:
            self.category_entry.set(self.product.category)
        else:
            self.category_entry.set("Produce")

        # Default Unit
        ctk.CTkLabel(self, text="Default Unit", font=ctk.CTkFont(size=13, weight="bold")).pack(padx=pad_x, anchor="w")
        self.unit_entry = ctk.CTkSegmentedButton(self, values=["lbs", "kg", "oz", "g"], height=35)
        self.unit_entry.pack(padx=pad_x, pady=(2, 20), fill="x")
        if self.product:
            self.unit_entry.set(self.product.default_unit)
        else:
            self.unit_entry.set("lbs")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=pad_x, pady=(0, 20), fill="x")

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray50", hover_color="gray40", command=self.destroy)
        cancel_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        save_btn = ctk.CTkButton(btn_frame, text="Save Product", fg_color="#007bff", hover_color="#0069d9", command=self._submit)
        save_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

    def _submit(self):
        name = self.name_entry.get().strip()
        category = self.category_entry.get().strip() or "General"
        unit = self.unit_entry.get().strip() or "lbs"

        if not name:
            messagebox.showwarning("Validation Error", "Please enter a product name.")
            return

        if self.product:
            self.product.name = name
            self.product.category = category
            self.product.default_unit = unit
            target_product = self.product
        else:
            target_product = FoodProduct(name=name, category=category, default_unit=unit)

        if self.on_save:
            self.on_save(target_product)
        self.destroy()
