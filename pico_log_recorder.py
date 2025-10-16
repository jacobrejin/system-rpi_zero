#!/usr/bin/env python3
# Cross-platform Pico USB-CDC log reader/recorder with auto-detect & auto-reconnect.
# Default backend: threads. Optional backend: asyncio.
import argparse
import os
import sys
import time
import threading
import queue
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports


DEFAULT_BAUD = 115200
DEFAULT_SESSION_MARKER = "::RPI-PICO-LOG::START"


def now_ts() -> str:
    return time.strftime("%d-%m-%Y %H:%M:%S")


def find_pico_port(
    preferred_port: Optional[str],
    vid: Optional[int],
    pid: Optional[int],
    product_hint: Optional[str],
    manufacturer_hint: Optional[str],
    platform_hint: str,
) -> Optional[str]:
    """
    Scan serial ports and return the first match.
    Matching criteria:
      - preferred_port if present
      - else VID (if provided) and optional PID
      - optional product/manufacturer substring hints (case-insensitive)
    """
    if preferred_port:
        return preferred_port

    ports = list(serial.tools.list_ports.comports())

    # Nice ordering: prefer TTY ACM/USB on Linux, COM on Windows
    def sort_key(p):
        dev = p.device
        if platform_hint == "windows":
            # Prefer lower COM numbers
            try:
                if dev.upper().startswith("COM"):
                    n = int(dev[3:])
                else:
                    n = 9999
            except Exception:
                n = 9999
            return (not dev.upper().startswith("COM"), n, dev)
        else:
            # linux/mac
            return (
                not (dev.startswith("/dev/ttyACM") or dev.startswith("/dev/ttyUSB")),
                dev,
            )

    ports.sort(key=sort_key)

    product_hint = (product_hint or "").lower()
    manufacturer_hint = (manufacturer_hint or "").lower()

    for p in ports:
        print(
            f"Checking port: {p.device}, VID: {p.vid}, PID: {p.pid}, Product: {p.product}, Manufacturer: {p.manufacturer}"
        )
        vid_ok = (vid is None) or (p.vid == vid)
        pid_ok = (pid is None) or (p.pid == pid)
        product_ok = (
            True if not product_hint else (product_hint in (p.product or "").lower())
        )
        manuf_ok = (
            True
            if not manufacturer_hint
            else (manufacturer_hint in (p.manufacturer or "").lower())
        )
        print(
            f"  vid_ok: {vid_ok}, pid_ok: {pid_ok}, product_ok: {product_ok}, manuf_ok: {manuf_ok}"
        )
        if vid_ok and pid_ok and product_ok and manuf_ok:
            print(f"Matched port: {p.device}")
            return p.device

    return None


class FileRecorder:
    """
    Writes lines to disk under logs/YYYY-MM-DD/.
    - If a session marker line arrives, rolls to a new session-N.log.
    - Otherwise writes to day.log.
    """

    def __init__(self, base_dir: Path, session_marker: str):
        self.base_dir = Path(base_dir)
        self.session_marker = session_marker
        self.cur_date = time.strftime("%d-%m-%Y")
        self.session_index = self._get_next_session_index()
        self.cur_file = None

    def _folder(self) -> Path:
        d = self.base_dir / self.cur_date
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _get_next_session_index(self) -> int:
        """Find the highest existing session number and return next index."""
        folder = self._folder()
        existing_sessions = list(folder.glob("session-*.log"))
        if not existing_sessions:
            return 1

        # Extract session numbers from filenames
        session_numbers = []
        for f in existing_sessions:
            try:
                # Extract number from "session-NNN.log"
                num_str = f.stem.replace("session-", "")
                session_numbers.append(int(num_str))
            except ValueError:
                continue

        if session_numbers:
            return max(session_numbers) + 1
        return 1

    # Removed day.log handling

    def _roll_session(self):
        if self.cur_file:
            self.cur_file.close()
        fname = f"session-{self.session_index:03d}.log"
        self.cur_file = open(self._folder() / fname, "a", encoding="utf-8", buffering=1)

    def _maybe_roll_date(self):
        today = time.strftime("%d-%m-%Y")
        if today != self.cur_date:
            # New date; create new session log
            if self.cur_file:
                self.cur_file.close()
            self.cur_date = today
            self.session_index = self._get_next_session_index()
            self._roll_session()

    def write_line(self, line: str):
        self._maybe_roll_date()
        if self.session_marker and self.session_marker in line:
            # If a file is already open, increment to create a new session
            if self.cur_file is not None:
                self.session_index += 1
                print(
                    f"[{now_ts()}] Session marker detected, rolling to session-{self.session_index:03d}.log",
                    flush=True,
                )
            else:
                print(
                    f"[{now_ts()}] First session marker detected, creating session-{self.session_index:03d}.log",
                    flush=True,
                )
            self._roll_session()
        else:
            if self.cur_file is None:
                self._roll_session()
            self.cur_file.write(f"{line}\n")
            self.cur_file.flush()

    def close(self):
        if self.cur_file:
            self.cur_file.close()
            self.cur_file = None


# -------------------------
# Threaded backend
# -------------------------
class SerialReaderThread(threading.Thread):
    def __init__(
        self, port_getter, baud, out_q: queue.Queue, stop_evt: threading.Event
    ):
        super().__init__(daemon=True)
        self.port_getter = port_getter
        self.baud = baud
        self.out_q = out_q
        self.stop_evt = stop_evt

    def run(self):
        backoff = 0.5
        while not self.stop_evt.is_set():
            port = self.port_getter()
            if not port:
                time.sleep(0.5)
                continue

            try:
                with serial.Serial(port, self.baud, timeout=0.1) as ser:
                    print(f"Connected: {port}", flush=True)
                    buf = bytearray()
                    backoff = 0.5  # reset backoff on success

                    # Handshake: send ::RPI-ZERO-LOG::READY until ::RPI-PICO-LOG::START is received
                    session_marker = DEFAULT_SESSION_MARKER
                    ready_msg = "::RPI-ZERO-LOG::READY\n".encode("utf-8")
                    found_marker = False
                    while not self.stop_evt.is_set() and not found_marker:
                        ser.write(ready_msg)
                        time.sleep(0.5)
                        chunk = ser.read(1024)
                        if chunk:
                            buf.extend(chunk)
                            while True:
                                nl = buf.find(b"\n")
                                if nl == -1:
                                    break
                                raw = buf[:nl]
                                del buf[: nl + 1]
                                if raw.endswith(b"\r"):
                                    raw = raw[:-1]
                                text = raw.decode("utf-8", errors="replace")
                                if session_marker in text:
                                    found_marker = True
                                    self.out_q.put(text)
                                    break

                    # Continue with normal reading
                    while not self.stop_evt.is_set():
                        try:
                            chunk = ser.read(1024)
                        except serial.SerialException as e:
                            print(f"Read error: {e}", flush=True)
                            break

                        if not chunk:
                            continue

                        buf.extend(chunk)
                        while True:
                            nl = buf.find(b"\n")
                            if nl == -1:
                                break
                            raw = buf[:nl]
                            del buf[: nl + 1]
                            if raw.endswith(b"\r"):
                                raw = raw[:-1]
                            text = raw.decode("utf-8", errors="replace")
                            self.out_q.put(text)

            except serial.SerialException as e:
                print(f"Open failed for {port}: {e}", flush=True)

            print(f"Disconnected, retrying...", flush=True)
            time.sleep(backoff)
            backoff = min(5.0, backoff * 1.5)


def run_threads(args):
    logs_dir = Path(args.log_dir).expanduser().resolve()
    recorder = FileRecorder(logs_dir, args.session_marker)

    # Port getter closure uses current args & auto-detect logic
    def _get_port():
        return find_pico_port(
            args.port,
            None if args.vid == 0 else args.vid,
            None if args.pid == 0 else args.pid,
            args.product,
            args.manufacturer,
            args.platform,
        )

    out_q: queue.Queue[str] = queue.Queue(maxsize=1000)
    stop_evt = threading.Event()

    reader = SerialReaderThread(_get_port, args.baud, out_q, stop_evt)
    reader.start()

    try:
        while True:
            try:
                line = out_q.get(timeout=0.5)
            except queue.Empty:
                continue
            # Print to console
            print(f"{line}", flush=True)
            # Record to file
            recorder.write_line(line)
    except KeyboardInterrupt:
        print(f"Exiting...", flush=True)
    finally:
        stop_evt.set()
        reader.join(timeout=2.0)
        recorder.close()


def main():
    parser = argparse.ArgumentParser(
        description="Pico USB-CDC non-blocking log recorder (Linux/Windows) with auto-reconnect."
    )

    parser.add_argument(
        "--platform",
        choices=["auto", "linux", "windows"],
        default="auto",
        help="Hint for device sorting; detection works regardless. Default: auto.",
    )
    parser.add_argument(
        "--port",
        help="Serial port (e.g., /dev/ttyACM0 or COM3). If omitted, auto-detect.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Baud rate. Default: {DEFAULT_BAUD}",
    )
    parser.add_argument(
        "--vid",
        type=lambda x: int(x, 0),
        default=0,
        help="USB Vendor ID to match (int, accepts 0x). Use 0 to ignore. Default: 0x2E8A",
    )
    parser.add_argument(
        "--pid",
        type=lambda x: int(x, 0),
        default=0,
        help="USB Product ID to match (int, accepts 0x). Use 0 to ignore.",
    )
    parser.add_argument(
        "--product",
        default="",
        help="Substring in USB product string (case-insensitive).",
    )
    parser.add_argument(
        "--manufacturer",
        default="",
        help="Substring in USB manufacturer string (case-insensitive).",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory to write logs into. Default: ./logs",
    )
    parser.add_argument(
        "--session-marker",
        default=DEFAULT_SESSION_MARKER,
        help=f"Marker that triggers a new session file. Default: {DEFAULT_SESSION_MARKER!r}",
    )
    args = parser.parse_args()

    if args.platform == "auto":
        if os.name == "nt":
            args.platform = "windows"
        else:
            args.platform = "linux"

    run_threads(args)


if __name__ == "__main__":
    main()
