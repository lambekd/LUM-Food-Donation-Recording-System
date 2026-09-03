"""Unit and integration test for core modules."""
import os
import sys
import tempfile
from core.models import Donor, FoodProduct, WeighRecord, ScaleConfig, SheetsConfig
from core.storage import Storage
from core.scale_reader import parse_scale_output, ScaleReader, unescape_command

# Ensure UTF-8 output safe
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run_tests():
    print("--- 1. Testing Storage & SQLite Persistence ---")
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    cfg_path = os.path.join(temp_dir, "test_settings.json")
    
    storage = Storage(db_path=db_path, config_path=cfg_path)
    
    # Donors
    donors = storage.get_all_donors()
    assert len(donors) >= 7, f"Expected >= 7 default donors, got {len(donors)}"
    new_donor_id = storage.add_donor(Donor(name="Sunny Bakery", category="Bakery", contact_info="sunny@example.com"))
    assert new_donor_id > 0
    updated_donors = storage.get_all_donors()
    assert any(d.name == "Sunny Bakery" for d in updated_donors)
    print(f"[OK] Donors CRUD test passed ({len(updated_donors)} donors)")

    # Products
    products = storage.get_all_products()
    assert len(products) >= 10, f"Expected >= 10 default products, got {len(products)}"
    new_prod_id = storage.add_product(FoodProduct(name="Organic Oats", category="Dry Goods", default_unit="lbs"))
    assert new_prod_id > 0
    updated_prods = storage.get_all_products()
    assert any(p.name == "Organic Oats" for p in updated_prods)
    print(f"[OK] Products CRUD test passed ({len(updated_prods)} products)")

    # Records
    rec = WeighRecord(
        donor_name="Sunny Bakery",
        product_name="Organic Oats",
        weight=24.75,
        unit="lbs",
        operator="Jane Doe",
        notes="Fresh morning batch"
    )
    rec_id = storage.add_record(rec)
    assert rec_id > 0
    recent = storage.get_recent_records()
    assert len(recent) == 1
    assert recent[0].weight == 24.75
    assert recent[0].donor_name == "Sunny Bakery"
    assert recent[0].synced_to_sheets is False
    print("[OK] Records CRUD test passed")

    # Mark synced
    storage.mark_record_synced(rec_id, True)
    recent = storage.get_recent_records()
    assert recent[0].synced_to_sheets is True
    print("[OK] Record sync status update passed")

    # Configs
    scale_cfg = ScaleConfig(port="COM7", baudrate=19200, use_simulator=True)
    storage.save_scale_config(scale_cfg)
    loaded_scale_cfg = storage.get_scale_config()
    assert loaded_scale_cfg.port == "COM7"
    assert loaded_scale_cfg.baudrate == 19200
    assert loaded_scale_cfg.use_simulator is True
    print("[OK] JSON Configuration persistence passed")

    print("\n--- 2. Testing Scale Parser ---")
    test_cases = [
        ("ST,GS,+  12.45kg", 12.45, "kg", True),
        ("US,GS,+   0.00kg", 0.0, "kg", False),
        ("  14.20 lb ", 14.20, "lbs", True),
        ("W: 5.20 OZ", 5.20, "oz", True),
        ("+0012.45 lb", 12.45, "lbs", True),
        ("10.50", 10.50, "lbs", True),
        ("0.450 kg", 0.45, "kg", True),
        ("500 g", 500.0, "g", True),
    ]
    for raw, exp_val, exp_unit, exp_stable in test_cases:
        val, unit, stable, clean = parse_scale_output(raw)
        assert val == exp_val, f"For '{raw}', expected {exp_val}, got {val}"
        assert unit == exp_unit, f"For '{raw}', expected {exp_unit}, got {unit}"
        assert stable == exp_stable, f"For '{raw}', expected {exp_stable}, got {stable}"
        print(f"[OK] Parsed: '{raw}' -> {val} {unit} (stable: {stable})")

    print("\n--- 3. Testing Scale Reader & Simulator ---")
    reader = ScaleReader(ScaleConfig(use_simulator=True))
    reader.start()
    reader.set_simulator_weight(18.75)
    val, unit, stable, raw = reader.read_weight_once()
    assert val is not None
    assert val > 0.0
    print(f"[OK] Scale Simulator read successfully: {val} {unit} ({raw})")
    reader.stop()

    print("\n--- 4. Testing Port Listing ---")
    ports = ScaleReader.list_available_ports()
    assert len(ports) >= 2, "Expected at least SIMULATOR and AUTO ports"
    print(f"[OK] Detected {len(ports)} port options (including virtual & auto options):")
    for p in ports:
        print(f"   * {p['name']}")

    print("\n--- ALL CORE TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    run_tests()
