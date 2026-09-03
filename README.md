# USB Scale to Google Sheets Desktop Application

A modern, high-performance desktop application for reading weights from USB/Serial digital scales, selecting customizable donors and food products, and storing transaction records into **Google Sheets** (with local offline SQLite caching).

---

## 🌟 Key Features

1. **Hardware & Scale Flexibility**:
   - Auto-detects all COM ports across any Windows / macOS / Linux computer.
   - Configurable baud rates (1200 to 115200), data bits, parity, stop bits, and query commands.
   - Robust ASCII parser for standard scales (Fairbanks, Mettler Toledo, Ohaus, Dymo, Brecknell, CAS, Tor Rey, and generic USB scales).
   - **Built-in Virtual Scale Simulator**: Allows full testing without needing physical scale hardware plugged in.

2. **Customizable Donor & Food Product Lists**:
   - **Donors Manager**: Add, edit, delete, categorize, and search donors.
   - **Food Products Manager**: Add, edit, delete, categorize, and assign default units (`lbs`, `kg`, `oz`, `g`).
   - Quick "+ Add" buttons directly on the weighing station for fast on-the-fly registration.

3. **High-Efficiency Weigh Station UI**:
   - Digital LCD-style weight readout.
   - Prominent **"Read Scale" / "Fetch Weight"** button.
   - Software Tare / Zero button.
   - Manual weight override mode.
   - One-click **"Save & Log to Google Sheet"** with instant visual feedback and audio cues.

4. **Dual Google Sheets Synchronization**:
   - **Method A: Google Apps Script Webhook (Easiest / 3 Minutes)**: Paste a Webhook URL from the included template. No Google Cloud Console setup required!
   - **Method B: Google Service Account (`credentials.json`)**: Direct API access via `gspread`.
   - **Offline Resilience**: If the internet is disconnected, all logs are safely stored locally in SQLite and can be batch synced anytime via **"Sync All to Sheets"**.

5. **History & CSV Export**:
   - Full history table with real-time sync indicators (`Synced` / `Pending Sync` / `Sync Error`).
   - Export all transaction logs to CSV with one click.

---

## 🚀 Getting Started

### 1. Installation

Ensure Python 3.9+ is installed. Clone or navigate to the project directory:

```bash
cd scale-sheets-app
python -m pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```

---

## 🔌 Scale & COM Port Configuration

1. Connect your USB scale to the computer.
2. In the app, open the **"Scale / COM Port"** tab.
3. Click **"↻ Refresh Ports"** and select your scale from the dropdown (e.g. `COM3 - USB Serial Device`).
4. Set the serial parameters matching your scale manual (standard is `9600 Baud, 8 Data Bits, Parity None, 1 Stop Bit`).
5. Choose **"Continuous Stream"** or **"Poll on Query"** (e.g. command `W\r\n` or `P\r\n`).
6. Click **"⚡ Test Query Scale Now"** to verify raw data is received and parsed.
7. Click **"Save Scale Settings & Reconnect"**.

> [!TIP]
> **No physical scale yet?** Toggle **"Enable Virtual Scale Simulator"** in the Scale tab to test the entire application and Google Sheets flow with realistic simulated weights.

---

## 📊 Google Sheets Setup (Choose Method A or B)

### Method A: Google Apps Script Webhook (Fastest & Recommended)

1. Open your target Google Sheet in your web browser.
2. Click **Extensions** > **Apps Script**.
3. Open [`assets/google_apps_script.js`](file:///C:/Users/kevin/.gemini/antigravity/scratch/scale-sheets-app/assets/google_apps_script.js), copy the contents, and paste it into the script editor.
4. Click **Deploy** > **New deployment**.
5. Select type: **Web app**.
6. Set:
   - **Execute as**: `Me`
   - **Who has access**: `Anyone`
7. Click **Deploy**, authorize permissions, and copy the **Web App URL** (starts with `https://script.google.com/macros/s/...`).
8. In the desktop app, go to **"Google Sheets Settings"**, select **Google Apps Script Webhook**, paste the URL, and click **"⚡ Test Google Sheets Connection"**.

---

### Method B: Google Cloud Service Account (`credentials.json`)

1. Create a Google Cloud Project with the **Google Sheets API** and **Google Drive API** enabled.
2. Create a Service Account, generate a JSON Key file, and save it on your computer.
3. Share your Google Sheet with the Service Account email address (give **Editor** permissions).
4. In the desktop app, go to **"Google Sheets Settings"**, choose **Google Service Account**, select your `credentials.json` file, enter the Sheet Name or Sheet URL, and click **"⚡ Test Google Sheets Connection"**.

---

## 📁 Project Structure

```
scale-sheets-app/
├── app.py                      # Main desktop application & tab layout
├── core/
│   ├── models.py               # Data classes (Donor, Product, WeighRecord, Configs)
│   ├── storage.py              # SQLite database and settings.json persistence
│   ├── scale_reader.py         # Hardware serial COM reader & scale simulator
│   └── sheets_sync.py          # Google Sheets API & background sync worker
├── ui/
│   ├── main_view.py            # Primary weigh & log form dashboard
│   ├── donor_manager.py        # Donor list manager & modal dialogs
│   ├── product_manager.py      # Food product list manager & modal dialogs
│   ├── history_view.py          # Transaction history table & CSV exporter
│   ├── scale_settings.py       # COM port selector & diagnostic monitor
│   └── sheets_settings.py      # Google Sheets connection settings
├── assets/
│   └── google_apps_script.js   # Ready-to-deploy Google Apps Script template
├── test_core.py                # Automated test suite for storage, scale & parsing
├── requirements.txt            # Python dependencies
└── README.md                   # Documentation and user guide
```
