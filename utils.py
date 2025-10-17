"""
Utility functions for the Pico Log Recorder system.
"""

import time
from typing import Optional
import serial.tools.list_ports

from config import TIMESTAMP_FORMAT


def now_ts() -> str:
    """Return current timestamp in DD-MM-YYYY HH:MM:SS format."""
    return time.strftime(TIMESTAMP_FORMAT)


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

    Args:
        preferred_port: Specific port to use if provided
        vid: USB Vendor ID to match (None to ignore)
        pid: USB Product ID to match (None to ignore)
        product_hint: Substring in USB product string
        manufacturer_hint: Substring in USB manufacturer string
        platform_hint: "windows" or "linux" for port sorting preference

    Returns:
        Port name (e.g., 'COM3' or '/dev/ttyACM0') or None if not found
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
            f"Checking port: {p.device}, VID: {p.vid}, PID: {p.pid}, "
            f"Product: {p.product}, Manufacturer: {p.manufacturer}"
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
            f"  vid_ok: {vid_ok}, pid_ok: {pid_ok}, "
            f"product_ok: {product_ok}, manuf_ok: {manuf_ok}"
        )
        if vid_ok and pid_ok and product_ok and manuf_ok:
            print(f"Matched port: {p.device}")
            return p.device

    return None
