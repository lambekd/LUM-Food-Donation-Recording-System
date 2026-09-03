"""
Scale Reader module for communicating with USB/Serial digital scales.
Supports auto-detection of COM ports, configurable serial parameters,
continuous background polling, on-demand query commands, robust ASCII
packet parsing, and a built-in virtual scale simulator.
"""
import re
import time
import random
import threading
from typing import List, Tuple, Optional, Callable, Dict, Any
import serial
import serial.tools.list_ports
from .models import ScaleConfig


# Common regex patterns for scale output
# Examples: "ST,GS,+  12.45kg", "  14.20 lb ", "W: 5.20 OZ", "+0012.45 lb", "10.50"
REGEX_WEIGHT = re.compile(
    r'(?P<prefix>[A-Za-z,_\s]*?)'
    r'(?P<sign>[+-])?'
    r'(?P<value>\d+\.?\d*|\.\d+)'
    r'\s*'
    r'(?P<unit>lbs?|kg|g|oz)?',
    re.IGNORECASE
)


def parse_scale_output(raw_str: str, default_unit: str = "lbs") -> Tuple[Optional[float], str, bool, str]:
    """
    Parses a raw scale ASCII string.
    Returns: (weight: float or None, unit: str, is_stable: bool, clean_raw: str)
    """
    if not raw_str:
        return None, default_unit, False, ""

    clean = raw_str.strip().replace("\x00", "").replace("\r", "").replace("\n", "")
    if not clean:
        return None, default_unit, False, ""

    # Check stability flags (common standard: 'ST' = Stable, 'US' = Unstable)
    is_stable = True
    if "US" in clean.upper() or "UNSTABLE" in clean.upper():
        is_stable = False

    # Search for numeric weight pattern
    match = REGEX_WEIGHT.search(clean)
    if match:
        try:
            val_str = match.group("value")
            sign = match.group("sign") or ""
            val = float(sign + val_str)
            
            raw_unit = match.group("unit")
            if raw_unit:
                unit = raw_unit.lower()
                if unit in ("lb", "lbs"):
                    unit = "lbs"
                elif unit in ("k", "kg", "kgs"):
                    unit = "kg"
                elif unit in ("g", "gm", "gms"):
                    unit = "g"
                elif unit in ("oz", "ozs"):
                    unit = "oz"
            else:
                unit = default_unit

            return val, unit, is_stable, clean
        except ValueError:
            pass

    return None, default_unit, False, clean


def unescape_command(cmd_str: str) -> bytes:
    """Converts a command string with escape sequences (e.g. 'W\\r\\n') into bytes."""
    if not cmd_str:
        return b"W\r\n"
    # Replace literal \r and \n if entered as text
    unescaped = (
        cmd_str.replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\x05", "\x05")  # ENQ
        .replace("\\x04", "\x04")  # EOT
    )
    return unescaped.encode("latin-1", errors="ignore")


class ScaleReader:
    def __init__(self, config: Optional[ScaleConfig] = None):
        self.config = config or ScaleConfig()
        self._serial: Optional[serial.Serial] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # State
        self.last_weight: Optional[float] = None
        self.last_unit: str = "lbs"
        self.is_stable: bool = True
        self.last_raw: str = ""
        self.last_update_time: float = 0.0
        self.is_connected: bool = False
        self.connection_status_text: str = "Disconnected"
        
        # Listeners for real-time updates
        self._listeners: List[Callable[[float, str, bool, str], None]] = []

        # Simulator state
        self._sim_weight = 12.50
        self._sim_fluctuation = 0.0

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        """Returns list of detected serial ports with descriptions."""
        ports = []
        # Add Special Simulator Option
        ports.append({
            "port": "SIMULATOR",
            "name": "Virtual Scale Simulator (Testing / No Hardware)",
            "description": "Simulates real-time scale measurements"
        })
        
        # Add Auto-Detect option
        ports.append({
            "port": "AUTO",
            "name": "Auto-Detect Scale Port",
            "description": "Automatically connect to first active serial port"
        })

        for p in serial.tools.list_ports.comports():
            desc = p.description or "Serial Device"
            hwid = p.hwid or ""
            ports.append({
                "port": p.device,
                "name": f"{p.device} - {desc}",
                "description": f"Hardware: {hwid}"
            })
        return ports

    def add_listener(self, callback: Callable[[float, str, bool, str], None]):
        """Register a callback for new weight readings."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[float, str, bool, str], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, weight: float, unit: str, is_stable: bool, raw: str):
        for cb in self._listeners:
            try:
                cb(weight, unit, is_stable, raw)
            except Exception as e:
                print(f"Error in scale listener: {e}")

    def start(self, config: Optional[ScaleConfig] = None):
        """Starts scale connection and background worker thread."""
        if config:
            self.config = config

        self.stop()

        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops reading and closes serial port."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._close_serial()
        self.is_connected = False
        self.connection_status_text = "Disconnected"

    def _close_serial(self):
        with self._lock:
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial = None

    def _open_port(self) -> bool:
        port_to_open = self.config.port

        if self.config.use_simulator or port_to_open.upper() == "SIMULATOR":
            self.is_connected = True
            self.connection_status_text = "Simulator Connected"
            return True

        if port_to_open.upper() == "AUTO":
            # Find first real COM port
            real_ports = [p.device for p in serial.tools.list_ports.comports()]
            if not real_ports:
                self.is_connected = False
                self.connection_status_text = "Auto-detect: No COM ports found"
                return False
            port_to_open = real_ports[0]

        try:
            parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
            stopbits_map = {1.0: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2.0: serial.STOPBITS_TWO}

            ser = serial.Serial(
                port=port_to_open,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=parity_map.get(self.config.parity, serial.PARITY_NONE),
                stopbits=stopbits_map.get(self.config.stopbits, serial.STOPBITS_ONE),
                timeout=self.config.timeout,
            )
            with self._lock:
                self._serial = ser
            self.is_connected = True
            self.connection_status_text = f"Connected ({port_to_open} @ {self.config.baudrate})"
            return True
        except Exception as e:
            self.is_connected = False
            self.connection_status_text = f"Error: {e}"
            return False

    def _worker_loop(self):
        """Background loop continuously reading or polling scale data."""
        reconnect_timer = 0
        while self._running:
            if not self.is_connected:
                now = time.time()
                if now - reconnect_timer > 3.0:
                    reconnect_timer = now
                    self._open_port()
                time.sleep(0.2)
                continue

            # Check if using simulator
            if self.config.use_simulator or self.config.port.upper() == "SIMULATOR":
                self._simulate_reading()
                time.sleep(0.3)
                continue

            # Read from real serial port
            try:
                if self.config.mode == "poll":
                    # Send poll command
                    cmd_bytes = unescape_command(self.config.poll_command)
                    with self._lock:
                        if self._serial and self._serial.is_open:
                            self._serial.write(cmd_bytes)
                            self._serial.flush()
                    time.sleep(0.1)

                line = ""
                with self._lock:
                    if self._serial and self._serial.is_open:
                        if self._serial.in_waiting > 0 or self.config.mode == "poll":
                            raw_line = self._serial.readline()
                            line = raw_line.decode("latin-1", errors="ignore").strip()

                if line:
                    val, unit, stable, clean = parse_scale_output(line)
                    if val is not None:
                        self.last_weight = val
                        self.last_unit = unit
                        self.is_stable = stable
                        self.last_raw = clean
                        self.last_update_time = time.time()
                        self._notify_listeners(val, unit, stable, clean)

                time.sleep(0.1)
            except Exception as e:
                self.is_connected = False
                self.connection_status_text = f"Connection Lost: {e}"
                self._close_serial()
                time.sleep(1.0)

    def _simulate_reading(self):
        """Simulates weight changes for testing."""
        # Random small jitter or stable value
        jitter = random.choice([0.0, 0.0, 0.0, 0.01, -0.01, 0.02])
        w = round(max(0.0, self._sim_weight + jitter), 2)
        unit = "lbs"
        stable = True
        raw = f"ST,GS,+  {w:06.2f} {unit}"
        self.last_weight = w
        self.last_unit = unit
        self.is_stable = stable
        self.last_raw = raw
        self.last_update_time = time.time()
        self._notify_listeners(w, unit, stable, raw)

    def set_simulator_weight(self, weight: float):
        """Helper to change the virtual scale weight."""
        self._sim_weight = max(0.0, weight)

    def read_weight_once(self) -> Tuple[Optional[float], str, bool, str]:
        """
        Actively fetches weight right now (triggered by the 'Read Scale' button).
        If already connected and receiving updates, returns the latest reading.
        If in poll mode on real serial, sends poll command and waits for response.
        """
        if self.config.use_simulator or self.config.port.upper() == "SIMULATOR":
            self._simulate_reading()
            return self.last_weight, self.last_unit, self.is_stable, self.last_raw

        if not self.is_connected:
            # Try to connect once
            success = self._open_port()
            if not success:
                return None, "lbs", False, self.connection_status_text

        # Try to read directly
        try:
            with self._lock:
                if self._serial and self._serial.is_open:
                    self._serial.reset_input_buffer()
                    cmd_bytes = unescape_command(self.config.poll_command)
                    self._serial.write(cmd_bytes)
                    self._serial.flush()
                    
                    # Read with short timeout
                    start_t = time.time()
                    while time.time() - start_t < 1.5:
                        if self._serial.in_waiting > 0:
                            line = self._serial.readline().decode("latin-1", errors="ignore").strip()
                            if line:
                                val, unit, stable, clean = parse_scale_output(line)
                                if val is not None:
                                    self.last_weight = val
                                    self.last_unit = unit
                                    self.is_stable = stable
                                    self.last_raw = clean
                                    self.last_update_time = time.time()
                                    return val, unit, stable, clean
                        time.sleep(0.05)

            # Fallback to last recorded weight if available and recent (< 3 seconds)
            if self.last_weight is not None and (time.time() - self.last_update_time < 3.0):
                return self.last_weight, self.last_unit, self.is_stable, self.last_raw

            return None, "lbs", False, "No response from scale"
        except Exception as e:
            return None, "lbs", False, f"Scale Read Error: {e}"
