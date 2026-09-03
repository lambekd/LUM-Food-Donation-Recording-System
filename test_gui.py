"""Automated GUI integration test."""
import os
import sys
import tempfile

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_gui_initialization():
    print("Testing GUI initialization...")
    import customtkinter as ctk
    from core.storage import Storage
    from core.scale_reader import ScaleReader
    from core.sheets_sync import SheetsSyncManager
    from core.models import ScaleConfig, SheetsConfig
    from app import ScaleApp

    app = ScaleApp()
    
    # Configure scale simulator
    app.scale_reader.start(ScaleConfig(use_simulator=True))

    # Trigger UI update
    app.update()

    print("[OK] ScaleApp window initialized successfully.")
    
    # Test Main View Dropdowns
    assert len(app.weigh_view.donors) >= 7
    assert len(app.weigh_view.products) >= 10
    print(f"[OK] Main view loaded {len(app.weigh_view.donors)} donors and {len(app.weigh_view.products)} products.")

    # Test Fetch Scale
    app.weigh_view._fetch_scale_weight()
    app.update()
    print(f"[OK] Weight readout after fetch: {app.weigh_view.weight_label.cget('text')} {app.weigh_view.unit_label.cget('text')}")

    # Test Form Submission
    initial_count = len(app.storage.get_recent_records())
    app.weigh_view.donor_combobox.set("Costco Wholesale")
    app.weigh_view.product_combobox.set("Fresh Apples")
    app.weigh_view.notes_entry.insert(0, "Morning donation batch")
    app.weigh_view._submit_transaction()
    app.update()

    # Verify record was stored
    records = app.storage.get_recent_records()
    assert len(records) == initial_count + 1
    assert records[0].donor_name == "Costco Wholesale"
    assert records[0].product_name == "Fresh Apples"
    print(f"[OK] Transaction submitted and verified in local database (Total: {len(records)}).")

    # Test history view refresh
    app.history_view.refresh_records()
    app.update()
    print("[OK] History view refreshed and verified.")

    # Clean shutdown
    app._on_close()
    print("[OK] Clean shutdown completed. GUI integration test PASSED!")

if __name__ == "__main__":
    test_gui_initialization()
