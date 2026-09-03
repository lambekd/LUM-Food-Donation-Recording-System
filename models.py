"""
Data models for the Scale to Google Sheets desktop application.
"""
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime


@dataclass
class Donor:
    id: Optional[int] = None
    name: str = ""
    category: str = "General"
    contact_info: str = ""
    is_active: bool = True

    def to_dict(self):
        return asdict(self)


@dataclass
class FoodProduct:
    id: Optional[int] = None
    name: str = ""
    category: str = "General"
    default_unit: str = "lbs"
    is_active: bool = True

    def to_dict(self):
        return asdict(self)


@dataclass
class WeighRecord:
    id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    donor_name: str = ""
    product_name: str = ""
    weight: float = 0.0
    unit: str = "lbs"
    notes: str = ""
    operator: str = ""
    synced_to_sheets: bool = False
    sync_error: str = ""

    def to_dict(self):
        return asdict(self)

    def to_sheet_row(self):
        """Returns row format suitable for Google Sheet columns."""
        return [
            self.timestamp,
            self.donor_name,
            self.product_name,
            round(self.weight, 2),
            self.unit,
            self.operator,
            self.notes,
        ]


@dataclass
class ScaleConfig:
    port: str = "AUTO"  # "AUTO", "COM1", etc. or "SIMULATOR"
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"  # 'N', 'E', 'O'
    stopbits: float = 1.0
    timeout: float = 1.0
    mode: str = "continuous"  # 'continuous' or 'poll'
    poll_command: str = "W\\r\\n"  # e.g., 'W\r\n', 'P\r\n', 'Q\r\n'
    use_simulator: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class SheetsConfig:
    auth_mode: str = "webhook"  # 'service_account', 'webhook', 'disabled'
    credentials_file: str = ""
    sheet_id_or_name: str = ""
    worksheet_name: str = "Sheet1"
    webhook_url: str = ""
    auto_sync: bool = True

    def to_dict(self):
        return asdict(self)
