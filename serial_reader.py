"""
Serial connection and reading logic for communicating with Raspberry Pi Pico.
"""

import time
import threading
import queue
import serial
import os
import glob
import shutil
import platform

import psutil
import ctypes

from config import (
    DEFAULT_SESSION_MARKER,
    READY_MESSAGE,
    SERIAL_TIMEOUT,
    SERIAL_READ_CHUNK_SIZE,
    INITIAL_BACKOFF,
    MAX_BACKOFF,
    RECONNECT_RETRY_INTERVAL,
    HANDSHAKE_SEND_INTERVAL,
    UPLOAD_FOLDER,
    PICO_DRIVE_LABEL,
    UPLOAD_COMMAND,
    UF2_DETECT_TIMEOUT,
    UF2_COPY_RETRY,
    UF2_COPY_WAIT,
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
        # Upload control primitives (can be triggered by external caller)
        self.upload_event = threading.Event()
        self.upload_lock = threading.Lock()
        self.upload_os_name = None

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

                    # Continue with normal reading; the upload can be requested
                    # while we're in the read loop. _read_loop will handle upload_event.
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
            # If an upload was requested, handle it (will close the serial port)
            if self.upload_event.is_set():
                try:
                    # Handle upload while we have an open serial object
                    self._handle_upload(ser)
                except Exception as e:
                    print(f"Upload handling error: {e}", flush=True)
                # break from read loop so outer context manager closes the port and
                # the run() loop can reconnect and re-handshake after reboot.
                break
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

    # Public API: request firmware upload. os_name can be passed (e.g., 'Windows').
    def request_firmware_upload(self, os_name: str = None):
        """Request a firmware upload to be performed by this thread.

        This sets an internal event which will be noticed inside the read loop
        and trigger the upload procedure using the currently-open serial port.
        """
        with self.upload_lock:
            self.upload_os_name = os_name or platform.system()
            # Ensure upload folder exists
            try:
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            except Exception:
                pass
            self.upload_event.set()

    def _handle_upload(self, ser: serial.Serial):
        """Perform the upload sequence using the currently-open serial object.

        Steps:
        - send the UPLOAD command so the Pico stops running user tasks
        - close the current serial connection
        - trigger UF2 bootloader by opening the port at 1200 baud
        - wait for the mass-storage drive to appear and copy UF2 files
        - clear upload_event and return (the run loop will re-open serial and
          perform the handshake again)
        """
        port = getattr(ser, "port", None)
        print("Upload requested, sending UPLOAD command to Pico...", flush=True)
        try:
            ser.write((UPLOAD_COMMAND + "\n").encode("utf-8"))
            ser.flush()
        except Exception as e:
            print(f"Failed to send upload command: {e}", flush=True)

        # Close the current serial to free the port for the 1200-baud trigger
        try:
            ser.close()
        except Exception:
            pass

        # Trigger bootloader by opening the port at 1200 baud (same approach
        # used in test.py). If port is None we fall back to calling port_getter.
        if not port:
            port = self.port_getter()

        if port:
            print(f"Triggering UF2 bootloader on port {port}...", flush=True)
            try:
                with serial.Serial(port, 1200) as trig:
                    # Opening and closing at 1200 should trigger UF2; give it a moment
                    pass
            except Exception as e:
                print(f"Bootloader trigger warning: {e}", flush=True)

        # Wait for the UF2 drive to appear and copy any .uf2 files from upload folder
        mount_point = self._wait_for_uf2_drive(timeout=UF2_DETECT_TIMEOUT)
        if not mount_point:
            print("UF2 drive not found; upload failed.", flush=True)
            self.upload_event.clear()
            return

        # Copy UF2 files
        uf2_files = glob.glob(os.path.join(UPLOAD_FOLDER, "*.uf2"))
        if not uf2_files:
            print(f"No .uf2 files found in {UPLOAD_FOLDER}", flush=True)
            self.upload_event.clear()
            return

        for uf2 in uf2_files:
            name = os.path.basename(uf2)
            dest = os.path.join(mount_point, name)
            success = False
            for attempt in range(UF2_COPY_RETRY):
                try:
                    print(
                        f"Copying {uf2} to {mount_point} (attempt {attempt + 1})...",
                        flush=True,
                    )
                    shutil.copy(uf2, mount_point)
                    success = True
                    break
                except Exception as e:
                    print(f"Copy attempt failed: {e}", flush=True)
                    time.sleep(UF2_COPY_WAIT)

            if success:
                print(f"Copied {name} to {mount_point}", flush=True)
            else:
                print(f"Failed to copy {name}", flush=True)

        # After copying, the Pico will reboot into the new firmware. Clear upload flag
        # and allow the outer loop to reconnect and perform handshake again.
        print("Upload sequence finished; waiting for Pico to reboot...", flush=True)
        self.upload_event.clear()

    def _wait_for_uf2_drive(self, timeout: float = 20.0):
        """Wait up to `timeout` seconds for a drive with the Pico label to appear.

        Returns the mountpoint (string) or None if not found.
        """
        deadline = time.time() + timeout
        while time.time() < deadline and not self.stop_evt.is_set():
            mount = self._find_pico_drive()
            if mount:
                return mount
            time.sleep(0.5)
        return None

    def _find_pico_drive(self):
        """Try to find the Pico UF2 drive by label or heuristics across platforms.

        Returns mountpoint string or None.
        """
        label = PICO_DRIVE_LABEL

        # Iterate disk partitions and match by volume label (Windows) or heuristics
        for part in psutil.disk_partitions(all=False):
            try:
                # On Windows, check volume label using WinAPI
                if platform.system() == "Windows":
                    try:
                        volume_name_buf = ctypes.create_unicode_buffer(1024)
                        fs_name_buf = ctypes.create_unicode_buffer(1024)
                        serial_number = ctypes.c_ulong()
                        max_component_length = ctypes.c_ulong()
                        file_system_flags = ctypes.c_ulong()
                        rc = ctypes.windll.kernel32.GetVolumeInformationW(
                            ctypes.c_wchar_p(part.device),
                            volume_name_buf,
                            ctypes.sizeof(volume_name_buf),
                            ctypes.byref(serial_number),
                            ctypes.byref(max_component_length),
                            ctypes.byref(file_system_flags),
                            fs_name_buf,
                            ctypes.sizeof(fs_name_buf),
                        )
                        if rc and volume_name_buf.value:
                            if label.lower() in volume_name_buf.value.lower():
                                return part.mountpoint
                    except Exception:
                        # Fall back to checking mountpoint or device name
                        pass

                # On other platforms, check mountpoint / device name heuristics
                if label.lower() in (part.device or "").lower():
                    return part.mountpoint
                if label.lower() in (part.mountpoint or "").lower():
                    return part.mountpoint

                # On many Linux systems the UF2 drive appears under /media or /run/media
                if part.mountpoint and (
                    "/media" in part.mountpoint or "/run/media" in part.mountpoint
                ):
                    # If the device is small and FAT, it's likely the UF2 drive
                    if part.fstype and part.fstype.lower().startswith("fat"):
                        return part.mountpoint
            except Exception:
                continue

        return None
