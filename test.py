import argparse
import serial
import time
import os
import shutil
import glob
import psutil
import platform
import ctypes


def get_volume_label_windows(drive_letter):
    """Return the volume label for a given Windows drive letter (e.g., 'E:\\')."""
    volume_name_buf = ctypes.create_unicode_buffer(1024)
    fs_name_buf = ctypes.create_unicode_buffer(1024)
    serial_number = ctypes.c_ulong()
    max_component_length = ctypes.c_ulong()
    file_system_flags = ctypes.c_ulong()

    rc = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(drive_letter),
        volume_name_buf,
        ctypes.sizeof(volume_name_buf),
        ctypes.byref(serial_number),
        ctypes.byref(max_component_length),
        ctypes.byref(file_system_flags),
        fs_name_buf,
        ctypes.sizeof(fs_name_buf),
    )
    if rc:
        return volume_name_buf.value
    return None


def find_pico_drive(label="RPI-RP2", timeout=20.0):
    """Find the Pico UF2 drive. Works on Windows and Linux/macOS with heuristics.

    Returns the mountpoint path or None if not found within timeout seconds.
    """
    deadline = time.time() + timeout
    system = platform.system()

    while time.time() < deadline:
        for part in psutil.disk_partitions(all=False):
            try:
                # Windows: check volume label via WinAPI
                if system == "Windows":
                    try:
                        # device usually like 'E:' or '\\?\\Volume{...}' — pass mountpoint for GetVolumeInformationW
                        label_name = get_volume_label_windows(part.device)
                        if label_name and label.lower() in label_name.lower():
                            return part.mountpoint
                    except Exception:
                        pass

                # Generic heuristics: mountpoint name contains label (e.g., /media/pi/RPI-RP2)
                mount_basename = os.path.basename(part.mountpoint.rstrip(os.sep))
                if mount_basename and label.lower() in mount_basename.lower():
                    return part.mountpoint

                # Many systems mount removable UF2 as FAT under /media or /run/media
                if part.mountpoint and (
                    "/media" in part.mountpoint or "/run/media" in part.mountpoint
                ):
                    if part.fstype and part.fstype.lower().startswith("fat"):
                        # optionally confirm by label on Windows only
                        return part.mountpoint
            except Exception:
                continue

        time.sleep(0.5)

    return None


def find_uf2_and_copy(upload_dir, mount_point, pattern="*.uf2"):
    files = glob.glob(os.path.join(upload_dir, pattern))
    if not files:
        print(f"No UF2 files found in {upload_dir}")
        return False

    for uf2 in files:
        try:
            print(f"Copying {uf2} -> {mount_point}")
            shutil.copy(uf2, mount_point)
            print("Copied", uf2)
        except Exception as e:
            print("Copy failed:", e)
            return False

    return True


def trigger_bootloader(port, baud_trigger=1200):
    try:
        with serial.Serial(port, baud_trigger) as s:
            # opening/closing triggers bootloader on RP2040
            pass
    except Exception as e:
        print("Warning: could not open serial to trigger bootloader:", e)


def main():
    parser = argparse.ArgumentParser(
        description="Trigger UF2 bootloader and copy .uf2 to Pico"
    )
    parser.add_argument(
        "--serial", "-s", help="Serial port device (e.g. COM5 or /dev/ttyACM0)"
    )
    parser.add_argument(
        "--uf2",
        "-u",
        help="Path to a .uf2 file to upload. If omitted, all .uf2 files in upload_binary/ are used.",
    )
    parser.add_argument(
        "--label",
        "-l",
        default="RPI-RP2",
        help="Volume label to look for on the UF2 drive (default: RPI-RP2)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=20.0,
        help="Seconds to wait for UF2 drive to appear (default: 20)",
    )
    args = parser.parse_args()

    upload_dir = os.path.join(os.getcwd(), "upload_binary")
    os.makedirs(upload_dir, exist_ok=True)

    serial_port = args.serial
    if not serial_port:
        # Try to guess a default on Linux (common device)
        if platform.system() == "Linux":
            # typical devices: /dev/ttyACM0, /dev/ttyUSB0
            for candidate in ("/dev/ttyACM0", "/dev/ttyUSB0"):
                if os.path.exists(candidate):
                    serial_port = candidate
                    break
        else:
            serial_port = None

    if not serial_port:
        print(
            "No serial port specified. Use --serial to pass the device (e.g. /dev/ttyACM0 or COM5)."
        )
        return

    print("Triggering Pico UF2 bootloader via serial port:", serial_port)
    trigger_bootloader(serial_port)

    print("Waiting for UF2 drive to appear...")
    mount_point = find_pico_drive(label=args.label, timeout=args.timeout)
    if not mount_point:
        print("Error: UF2 drive not found within timeout")
        return

    print("UF2 drive found at:", mount_point)

    # If a specific uf2 path was given use that, otherwise copy all in upload_binary
    if args.uf2:
        uf2_path = args.uf2
        if not os.path.exists(uf2_path):
            print("Specified UF2 file does not exist:", uf2_path)
            return
        print("Copying", uf2_path, "->", mount_point)
        try:
            shutil.copy(uf2_path, mount_point)
            print("Copy successful")
        except Exception as e:
            print("Copy failed:", e)
            return
    else:
        ok = find_uf2_and_copy(upload_dir, mount_point)
        if not ok:
            print("No files copied; ensure a .uf2 exists in upload_binary/")
            return

    print("Done. Waiting a few seconds for Pico to reboot...")
    time.sleep(3)
    print("Finished.")


if __name__ == "__main__":
    main()
