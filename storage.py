"""
Storage module managing local SQLite database and JSON configurations.
"""
import os
import json
import sqlite3
from typing import List, Optional, Dict, Any
from .models import Donor, FoodProduct, WeighRecord, ScaleConfig, SheetsConfig


DEFAULT_DONORS = [
    ("Costco Wholesale", "Retailer", "manager@costco.example"),
    ("Trader Joe's", "Grocery", "donations@traderjoes.example"),
    ("Whole Foods Market", "Grocery", "support@wholefoods.example"),
    ("Target Superstore", "Retailer", "community@target.example"),
    ("Local Community Garden", "Farm/Garden", "garden@community.org"),
    ("Main Street Bakery", "Bakery", "orders@mainstreetbakery.example"),
    ("Valley Dairy Co.", "Dairy", "contact@valleydairy.example"),
]

DEFAULT_PRODUCTS = [
    ("Fresh Apples", "Produce", "lbs"),
    ("Bananas", "Produce", "lbs"),
    ("Oranges & Citrus", "Produce", "lbs"),
    ("Leafy Greens & Lettuce", "Produce", "lbs"),
    ("Carrots & Root Veggies", "Produce", "lbs"),
    ("Canned Soup & Vegetables", "Canned Goods", "lbs"),
    ("Dry Rice & Grains", "Dry Goods", "lbs"),
    ("Pasta & Noodles", "Dry Goods", "lbs"),
    ("Whole Grain Bread", "Bakery", "lbs"),
    ("Fresh Milk & Dairy", "Dairy", "lbs"),
    ("Poultry & Chicken", "Meat/Protein", "lbs"),
    ("Frozen Prepared Meals", "Frozen", "lbs"),
]


class Storage:
    def __init__(self, db_path: Optional[str] = None, config_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.path.join(base_dir, "scale_app.db")
        self.config_path = config_path or os.path.join(base_dir, "settings.json")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Donors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS donors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT DEFAULT 'General',
                    contact_info TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Food products table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS food_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT DEFAULT 'General',
                    default_unit TEXT DEFAULT 'lbs',
                    is_active INTEGER DEFAULT 1
                )
            """)

            # Records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    donor_name TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    weight REAL NOT NULL,
                    unit TEXT NOT NULL DEFAULT 'lbs',
                    notes TEXT DEFAULT '',
                    operator TEXT DEFAULT '',
                    synced_to_sheets INTEGER DEFAULT 0,
                    sync_error TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default donors if table is empty
            cursor.execute("SELECT COUNT(*) FROM donors")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO donors (name, category, contact_info) VALUES (?, ?, ?)",
                    DEFAULT_DONORS
                )

            # Seed default products if table is empty
            cursor.execute("SELECT COUNT(*) FROM food_products")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO food_products (name, category, default_unit) VALUES (?, ?, ?)",
                    DEFAULT_PRODUCTS
                )
            conn.commit()

    # --- Donor Operations ---

    def get_all_donors(self, active_only: bool = True) -> List[Donor]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT id, name, category, contact_info, is_active FROM donors WHERE is_active = 1 ORDER BY name ASC")
            else:
                cursor.execute("SELECT id, name, category, contact_info, is_active FROM donors ORDER BY name ASC")
            rows = cursor.fetchall()
            return [
                Donor(
                    id=row["id"],
                    name=row["name"],
                    category=row["category"],
                    contact_info=row["contact_info"],
                    is_active=bool(row["is_active"])
                )
                for row in rows
            ]

    def add_donor(self, donor: Donor) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO donors (name, category, contact_info, is_active) VALUES (?, ?, ?, ?)",
                (donor.name.strip(), donor.category.strip(), donor.contact_info.strip(), 1 if donor.is_active else 0)
            )
            conn.commit()
            return cursor.lastrowid

    def update_donor(self, donor: Donor) -> bool:
        if donor.id is None:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE donors SET name = ?, category = ?, contact_info = ?, is_active = ? WHERE id = ?",
                (donor.name.strip(), donor.category.strip(), donor.contact_info.strip(), 1 if donor.is_active else 0, donor.id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_donor(self, donor_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM donors WHERE id = ?", (donor_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Food Product Operations ---

    def get_all_products(self, active_only: bool = True) -> List[FoodProduct]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("SELECT id, name, category, default_unit, is_active FROM food_products WHERE is_active = 1 ORDER BY name ASC")
            else:
                cursor.execute("SELECT id, name, category, default_unit, is_active FROM food_products ORDER BY name ASC")
            rows = cursor.fetchall()
            return [
                FoodProduct(
                    id=row["id"],
                    name=row["name"],
                    category=row["category"],
                    default_unit=row["default_unit"],
                    is_active=bool(row["is_active"])
                )
                for row in rows
            ]

    def add_product(self, product: FoodProduct) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO food_products (name, category, default_unit, is_active) VALUES (?, ?, ?, ?)",
                (product.name.strip(), product.category.strip(), product.default_unit.strip(), 1 if product.is_active else 0)
            )
            conn.commit()
            return cursor.lastrowid

    def update_product(self, product: FoodProduct) -> bool:
        if product.id is None:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE food_products SET name = ?, category = ?, default_unit = ?, is_active = ? WHERE id = ?",
                (product.name.strip(), product.category.strip(), product.default_unit.strip(), 1 if product.is_active else 0, product.id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_product(self, product_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM food_products WHERE id = ?", (product_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Weigh Records Operations ---

    def add_record(self, record: WeighRecord) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO records 
                (timestamp, donor_name, product_name, weight, unit, notes, operator, synced_to_sheets, sync_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.timestamp,
                    record.donor_name,
                    record.product_name,
                    record.weight,
                    record.unit,
                    record.notes,
                    record.operator,
                    1 if record.synced_to_sheets else 0,
                    record.sync_error
                )
            )
            conn.commit()
            record.id = cursor.lastrowid
            return cursor.lastrowid

    def get_recent_records(self, limit: int = 100) -> List[WeighRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM records ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                WeighRecord(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    donor_name=row["donor_name"],
                    product_name=row["product_name"],
                    weight=row["weight"],
                    unit=row["unit"],
                    notes=row["notes"],
                    operator=row["operator"],
                    synced_to_sheets=bool(row["synced_to_sheets"]),
                    sync_error=row["sync_error"] or ""
                )
                for row in rows
            ]

    def get_unsynced_records(self) -> List[WeighRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM records WHERE synced_to_sheets = 0 ORDER BY id ASC")
            rows = cursor.fetchall()
            return [
                WeighRecord(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    donor_name=row["donor_name"],
                    product_name=row["product_name"],
                    weight=row["weight"],
                    unit=row["unit"],
                    notes=row["notes"],
                    operator=row["operator"],
                    synced_to_sheets=bool(row["synced_to_sheets"]),
                    sync_error=row["sync_error"] or ""
                )
                for row in rows
            ]

    def mark_record_synced(self, record_id: int, synced: bool = True, error: str = "") -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE records SET synced_to_sheets = ?, sync_error = ? WHERE id = ?",
                (1 if synced else 0, error, record_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_record(self, record_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_records(self) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM records")
            conn.commit()
            return True

    # --- Configuration (JSON) Operations ---

    def _read_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_config(self, data: Dict[str, Any]):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving config to {self.config_path}: {e}")

    def get_scale_config(self) -> ScaleConfig:
        data = self._read_config().get("scale", {})
        return ScaleConfig(
            port=data.get("port", "AUTO"),
            baudrate=data.get("baudrate", 9600),
            bytesize=data.get("bytesize", 8),
            parity=data.get("parity", "N"),
            stopbits=data.get("stopbits", 1.0),
            timeout=data.get("timeout", 1.0),
            mode=data.get("mode", "continuous"),
            poll_command=data.get("poll_command", "W\\r\\n"),
            use_simulator=data.get("use_simulator", False),
        )

    def save_scale_config(self, cfg: ScaleConfig):
        data = self._read_config()
        data["scale"] = cfg.to_dict()
        self._write_config(data)

    def get_sheets_config(self) -> SheetsConfig:
        data = self._read_config().get("sheets", {})
        return SheetsConfig(
            auth_mode=data.get("auth_mode", "webhook"),
            credentials_file=data.get("credentials_file", ""),
            sheet_id_or_name=data.get("sheet_id_or_name", ""),
            worksheet_name=data.get("worksheet_name", "Sheet1"),
            webhook_url=data.get("webhook_url", ""),
            auto_sync=data.get("auto_sync", True),
        )

    def save_sheets_config(self, cfg: SheetsConfig):
        data = self._read_config()
        data["sheets"] = cfg.to_dict()
        self._write_config(data)

    def get_general_settings(self) -> Dict[str, Any]:
        return self._read_config().get("general", {
            "default_unit": "lbs",
            "operator_name": "Operator 1",
            "theme": "dark",
            "auto_tare": False
        })

    def save_general_settings(self, settings: Dict[str, Any]):
        data = self._read_config()
        data["general"] = settings
        self._write_config(data)
