"""
Serial connection and reading logic for communicating with Raspberry Pi Pico.
"""

import time
import threading
import queue
import serial

from config import (
    DEFAULT_SESSION_MARKER,
    READY_MESSAGE,
    SERIAL_TIMEOUT,
    SERIAL_READ_CHUNK_SIZE,
    INITIAL_BACKOFF,
    MAX_BACKOFF,
    RECONNECT_RETRY_INTERVAL,
    HANDSHAKE_SEND_INTERVAL,
)


class SerialReaderThread(threading.Thread):
    """
    Thread that continuously reads from serial port with auto-reconnect.

    Handles:
    - Initial handshake with Pico (send READY, wait for START marker)
    - Line buffering and decoding
    - Auto-reconnect with exponential backoff on disconnect
    - Graceful shutdown via stop event
    """

    def __init__(
        self, port_getter, baud: int, out_q: queue.Queue, stop_evt: threading.Event
    ):
        """
        Initialize serial reader thread.

        Args:
            port_getter: Callable that returns port name (or None)
            baud: Baud rate for serial connection
            out_q: Queue to put decoded lines into
            stop_evt: Event to signal thread shutdown
        """
        super().__init__(daemon=True)
        self.port_getter = port_getter
        self.baud = baud
        self.out_q = out_q
        self.stop_evt = stop_evt

    def run(self):
        """Main thread loop - connect, read, reconnect on failure."""
        backoff = INITIAL_BACKOFF

        while not self.stop_evt.is_set():
            port = self.port_getter()
            if not port:
                time.sleep(RECONNECT_RETRY_INTERVAL)
                continue

            try:
                with serial.Serial(port, self.baud, timeout=SERIAL_TIMEOUT) as ser:
                    print(f"Connected: {port}", flush=True)
                    buf = bytearray()
                    backoff = INITIAL_BACKOFF  # reset backoff on success

                    # Handshake: send READY until START marker is received
                    if not self._perform_handshake(ser, buf):
                        continue  # Handshake failed or stop requested

                    # Continue with normal reading
                    self._read_loop(ser, buf)

            except serial.SerialException as e:
                print(f"Open failed for {port}: {e}", flush=True)

            print(f"Disconnected, retrying...", flush=True)
            time.sleep(backoff)
            backoff = min(MAX_BACKOFF, backoff * 1.5)

    def _perform_handshake(self, ser: serial.Serial, buf: bytearray) -> bool:
        """
        Perform handshake with Pico.

        Sends READY message repeatedly until START marker is received.

        Args:
            ser: Open serial connection
            buf: Buffer for accumulating data

        Returns:
            True if handshake successful, False if stopped or failed
        """
        session_marker = DEFAULT_SESSION_MARKER
        ready_msg = f"{READY_MESSAGE}\n".encode("utf-8")
        found_marker = False

        while not self.stop_evt.is_set() and not found_marker:
            ser.write(ready_msg)
            time.sleep(HANDSHAKE_SEND_INTERVAL)
            chunk = ser.read(SERIAL_READ_CHUNK_SIZE)

            if chunk:
                buf.extend(chunk)
                # Process all complete lines in buffer
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

        return found_marker

    def _read_loop(self, ser: serial.Serial, buf: bytearray):
        """
        Main reading loop after handshake.

        Args:
            ser: Open serial connection
            buf: Buffer for accumulating data
        """
        while not self.stop_evt.is_set():
            try:
                chunk = ser.read(SERIAL_READ_CHUNK_SIZE)
            except serial.SerialException as e:
                print(f"Read error: {e}", flush=True)
                break

            if not chunk:
                continue

            buf.extend(chunk)
            # Process all complete lines in buffer
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
