"""
Scale and COM port configuration interface.
Provides device-flexible serial port management, baud rates, parity,
continuous/poll mode, command testing, and Virtual Scale Simulator.
"""
import customtkinter as ctk
from tkinter import messagebox
from typing import Dict, List, Optional
from core.models import ScaleConfig
from core.storage import Storage
from core.scale_reader import ScaleReader


class ScaleSettingsFrame(ctk.CTkFrame):
    def __init__(self, master, storage: Storage, scale_reader: ScaleReader, on_scale_reconnected: Optional[callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.storage = storage
        self.scale_reader = scale_reader
        self.on_scale_reconnected = on_scale_reconnected
        self.config: ScaleConfig = storage.get_scale_config()
        self.detected_ports: List[Dict[str, str]] = []

        self._build_ui()
        self.refresh_ports_list()
        self._load_values()

    def _build_ui(self):
        # Header
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            top_bar,
            text="Scale & COM Port Settings",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left")

        # Main scrollable settings area
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # --- Section 1: Port Selection ---
        port_card = ctk.CTkFrame(scroll)
        port_card.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(port_card, text="Serial / COM Port Connection", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 6))

        port_row = ctk.CTkFrame(port_card, fg_color="transparent")
        port_row.pack(fill="x", padx=15, pady=(0, 12))

        self.port_combobox = ctk.CTkComboBox(port_row, values=["Scanning..."], width=360, height=36)
        self.port_combobox.pack(side="left", fill="x", expand=True, padx=(0, 10))

        refresh_ports_btn = ctk.CTkButton(port_row, text="↻ Refresh Ports", width=120, height=36, command=self.refresh_ports_list)
        refresh_ports_btn.pack(side="right")

        # Simulator Switch
        self.sim_switch = ctk.CTkSwitch(
            port_card,
            text="Enable Virtual Scale Simulator (for testing without physical scale hardware)",
            font=ctk.CTkFont(size=13),
            command=self._on_toggle_simulator
        )
        self.sim_switch.pack(anchor="w", padx=15, pady=(0, 12))

        # Simulator weight test slider
        self.sim_control_frame = ctk.CTkFrame(port_card, fg_color="transparent")
        self.sim_control_frame.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkLabel(self.sim_control_frame, text="Simulated Weight:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 10))
        self.sim_slider = ctk.CTkSlider(self.sim_control_frame, from_=0.5, to=150.0, number_of_steps=299, command=self._on_sim_slider_change)
        self.sim_slider.set(12.5)
        self.sim_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.sim_val_lbl = ctk.CTkLabel(self.sim_control_frame, text="12.50 lbs", font=ctk.CTkFont(size=13, weight="bold"), width=70)
        self.sim_val_lbl.pack(side="right")

        # --- Section 2: Serial Protocol Parameters ---
        param_card = ctk.CTkFrame(scroll)
        param_card.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(param_card, text="Serial Communication Parameters", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 10))

        grid_frame = ctk.CTkFrame(param_card, fg_color="transparent")
        grid_frame.pack(fill="x", padx=15, pady=(0, 12))

        # Baud Rate
        ctk.CTkLabel(grid_frame, text="Baud Rate:").grid(row=0, column=0, sticky="w", padx=5, pady=6)
        self.baud_menu = ctk.CTkComboBox(grid_frame, values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"], width=130)
        self.baud_menu.grid(row=0, column=1, sticky="w", padx=5, pady=6)

        # Data Bits
        ctk.CTkLabel(grid_frame, text="Data Bits:").grid(row=0, column=2, sticky="w", padx=(20, 5), pady=6)
        self.databits_menu = ctk.CTkComboBox(grid_frame, values=["7", "8"], width=100)
        self.databits_menu.grid(row=0, column=3, sticky="w", padx=5, pady=6)

        # Parity
        ctk.CTkLabel(grid_frame, text="Parity:").grid(row=1, column=0, sticky="w", padx=5, pady=6)
        self.parity_menu = ctk.CTkComboBox(grid_frame, values=["None (N)", "Even (E)", "Odd (O)"], width=130)
        self.parity_menu.grid(row=1, column=1, sticky="w", padx=5, pady=6)

        # Stop Bits
        ctk.CTkLabel(grid_frame, text="Stop Bits:").grid(row=1, column=2, sticky="w", padx=(20, 5), pady=6)
        self.stopbits_menu = ctk.CTkComboBox(grid_frame, values=["1", "1.5", "2"], width=100)
        self.stopbits_menu.grid(row=1, column=3, sticky="w", padx=5, pady=6)

        # Reading Mode
        ctk.CTkLabel(grid_frame, text="Reading Mode:").grid(row=2, column=0, sticky="w", padx=5, pady=6)
        self.mode_menu = ctk.CTkSegmentedButton(grid_frame, values=["Continuous Stream", "Poll on Query"], command=self._on_mode_change)
        self.mode_menu.grid(row=2, column=1, columnspan=3, sticky="w", padx=5, pady=6)

        # Poll Command
        self.poll_row = ctk.CTkFrame(param_card, fg_color="transparent")
        self.poll_row.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkLabel(self.poll_row, text="Scale Query Command:").pack(side="left", padx=(0, 10))
        self.poll_cmd_entry = ctk.CTkEntry(self.poll_row, placeholder_text="e.g. W\\r\\n, P\\r\\n, Q\\r\\n", width=180)
        self.poll_cmd_entry.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(self.poll_row, text="(Sent to scale to request weight)", text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left")

        # --- Section 3: Diagnostic & Live Test Monitor ---
        diag_card = ctk.CTkFrame(scroll)
        diag_card.pack(fill="x", pady=8, padx=5)

        ctk.CTkLabel(diag_card, text="Hardware Diagnostic & Test Monitor", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(12, 8))

        diag_btn_row = ctk.CTkFrame(diag_card, fg_color="transparent")
        diag_btn_row.pack(fill="x", padx=15, pady=(0, 10))

        test_btn = ctk.CTkButton(
            diag_btn_row,
            text="⚡ Test Query Scale Now",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#17a2b8",
            hover_color="#138496",
            command=self._test_scale_read
        )
        test_btn.pack(side="left", padx=(0, 10))

        self.diag_status_lbl = ctk.CTkLabel(diag_btn_row, text="Status: Ready to test", text_color="gray")
        self.diag_status_lbl.pack(side="left")

        self.diag_output_box = ctk.CTkTextbox(diag_card, height=90, font=ctk.CTkFont(family="Consolas", size=12))
        self.diag_output_box.pack(fill="x", padx=15, pady=(0, 15))
        self.diag_output_box.insert("1.0", "Click 'Test Query Scale Now' to verify scale communication and raw data parsing...\n")

        # Save Button Bar
        bottom_bar = ctk.CTkFrame(scroll, fg_color="transparent")
        bottom_bar.pack(fill="x", pady=(15, 10))

        save_btn = ctk.CTkButton(
            bottom_bar,
            text="Save Scale Settings & Reconnect",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#007bff",
            hover_color="#0069d9",
            height=40,
            command=self._save_settings
        )
        save_btn.pack(side="right", padx=5)

    def refresh_ports_list(self):
        self.detected_ports = ScaleReader.list_available_ports()
        display_values = [p["name"] for p in self.detected_ports]
        self.port_combobox.configure(values=display_values)

        # Set matching port if possible
        target_port = self.config.port
        found_idx = 0
        for idx, p in enumerate(self.detected_ports):
            if p["port"] == target_port:
                found_idx = idx
                break
        if display_values:
            self.port_combobox.set(display_values[found_idx])

    def _load_values(self):
        self.baud_menu.set(str(self.config.baudrate))
        self.databits_menu.set(str(self.config.bytesize))
        
        parity_display = "None (N)"
        if self.config.parity == "E":
            parity_display = "Even (E)"
        elif self.config.parity == "O":
            parity_display = "Odd (O)"
        self.parity_menu.set(parity_display)

        self.stopbits_menu.set(str(int(self.config.stopbits) if self.config.stopbits == 1.0 or self.config.stopbits == 2.0 else self.config.stopbits))
        self.mode_menu.set("Continuous Stream" if self.config.mode == "continuous" else "Poll on Query")
        self.poll_cmd_entry.delete(0, "end")
        self.poll_cmd_entry.insert(0, self.config.poll_command)

        if self.config.use_simulator:
            self.sim_switch.select()
        else:
            self.sim_switch.deselect()

    def _on_toggle_simulator(self):
        is_sim = self.sim_switch.get() == 1
        if is_sim:
            self.sim_slider.configure(state="normal")
            self.scale_reader.set_simulator_weight(self.sim_slider.get())
        else:
            pass

    def _on_sim_slider_change(self, val):
        self.sim_val_lbl.configure(text=f"{val:.2f} lbs")
        self.scale_reader.set_simulator_weight(val)

    def _on_mode_change(self, value):
        pass

    def _test_scale_read(self):
        # Save temp config to test reader
        cfg = self._build_config_from_ui()
        self.scale_reader.start(cfg)
        
        val, unit, stable, raw = self.scale_reader.read_weight_once()
        self.diag_output_box.delete("1.0", "end")
        
        log_txt = f"--- Diagnostic Test at {self.scale_reader.connection_status_text} ---\n"
        log_txt += f"Port: {cfg.port} | Baud: {cfg.baudrate} | Mode: {cfg.mode}\n"
        log_txt += f"Raw Input Received: '{raw}'\n"
        if val is not None:
            log_txt += f"Parsed Weight: {val:.2f} {unit.upper()}\n"
            log_txt += f"Stability: {'[STABLE]' if stable else '[UNSTABLE / FLUCTUATING]'}\n"
            self.diag_status_lbl.configure(text=f"Status: Success ({val:.2f} {unit})", text_color="#28a745")
        else:
            log_txt += f"Parsed Result: None (Check COM port, wiring, or baud rate)\n"
            self.diag_status_lbl.configure(text="Status: No valid data received", text_color="#dc3545")

        self.diag_output_box.insert("1.0", log_txt)

    def _build_config_from_ui(self) -> ScaleConfig:
        selected_name = self.port_combobox.get()
        actual_port = "AUTO"
        for p in self.detected_ports:
            if p["name"] == selected_name:
                actual_port = p["port"]
                break

        baud = int(self.baud_menu.get())
        bytesize = int(self.databits_menu.get())
        
        p_val = self.parity_menu.get()
        parity = "N"
        if "Even" in p_val:
            parity = "E"
        elif "Odd" in p_val:
            parity = "O"

        stopbits = float(self.stopbits_menu.get())
        mode = "continuous" if self.mode_menu.get() == "Continuous Stream" else "poll"
        poll_cmd = self.poll_cmd_entry.get()
        use_sim = self.sim_switch.get() == 1 or actual_port == "SIMULATOR"

        return ScaleConfig(
            port=actual_port,
            baudrate=baud,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            mode=mode,
            poll_command=poll_cmd,
            use_simulator=use_sim
        )

    def _save_settings(self):
        new_cfg = self._build_config_from_ui()
        self.storage.save_scale_config(new_cfg)
        self.config = new_cfg
        self.scale_reader.start(new_cfg)

        if self.on_scale_reconnected:
            self.on_scale_reconnected()

        messagebox.showinfo("Saved", "Scale settings saved and connection refreshed!")
