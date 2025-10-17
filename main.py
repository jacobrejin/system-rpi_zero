#!/usr/bin/env python3
"""
Main entry point for Pico Log Recorder system.
Orchestrates serial reading, file recording, and (future) server uploads.
"""

import argparse
import os
import queue
import threading
from pathlib import Path

from config import (
    DEFAULT_BAUD,
    DEFAULT_SESSION_MARKER,
    DEFAULT_LOG_DIR,
    QUEUE_MAX_SIZE,
    QUEUE_TIMEOUT,
    THREAD_JOIN_TIMEOUT,
)
from utils import find_pico_port
from serial_reader import SerialReaderThread
from log_manager import FileRecorder


def run_threads(args):
    """
    Main orchestration function - sets up and runs all threads.

    Args:
        args: Parsed command-line arguments
    """
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

    out_q: queue.Queue[str] = queue.Queue(maxsize=QUEUE_MAX_SIZE)
    stop_evt = threading.Event()

    reader = SerialReaderThread(_get_port, args.baud, out_q, stop_evt)
    reader.start()

    try:
        while True:
            try:
                line = out_q.get(timeout=QUEUE_TIMEOUT)
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
        reader.join(timeout=THREAD_JOIN_TIMEOUT)
        recorder.close()


def main():
    """Parse arguments and start the system."""
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
        default=DEFAULT_LOG_DIR,
        help=f"Directory to write logs into. Default: {DEFAULT_LOG_DIR}",
    )
    parser.add_argument(
        "--session-marker",
        default=DEFAULT_SESSION_MARKER,
        help=f"Marker that triggers a new session file. Default: {DEFAULT_SESSION_MARKER!r}",
    )

    args = parser.parse_args()

    # Auto-detect platform if not specified
    if args.platform == "auto":
        if os.name == "nt":
            args.platform = "windows"
        else:
            args.platform = "linux"

    run_threads(args)


if __name__ == "__main__":
    main()
