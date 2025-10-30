import argparse
import serial
import time
import os
import shutil
import glob
import psutil
import platform
import ctypes
import subprocess


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
    """
    Find (and if necessary mount) the Raspberry Pi Pico UF2 drive.
    Works on Linux (Raspbian) and Windows.
    Returns the mount point path or None if not found within timeout.
    """
    deadline = time.time() + timeout
    system = platform.system()

    while time.time() < deadline:
        # --- Step 1: Check already-mounted drives ---
        for part in psutil.disk_partitions(all=False):
            try:
                # Windows: match by volume label
                if system == "Windows":
                    from ctypes import (
                        create_unicode_buffer,
                        c_ulong,
                        byref,
                        windll,
                        c_wchar_p,
                        sizeof,
                    )

                    volume_name_buf = create_unicode_buffer(1024)
                    fs_name_buf = create_unicode_buffer(1024)
                    serial_number = c_ulong()
                    max_component_length = c_ulong()
                    file_system_flags = c_ulong()
                    rc = windll.kernel32.GetVolumeInformationW(
                        c_wchar_p(part.device),
                        volume_name_buf,
                        sizeof(volume_name_buf),
                        byref(serial_number),
                        byref(max_component_length),
                        byref(file_system_flags),
                        fs_name_buf,
                        sizeof(fs_name_buf),
                    )
                    if rc and label.lower() in volume_name_buf.value.lower():
                        return part.mountpoint
                else:
                    # Linux / macOS: match by mount path name
                    mount_basename = os.path.basename(part.mountpoint.rstrip(os.sep))
                    if label.lower() in mount_basename.lower():
                        return part.mountpoint
            except Exception:
                continue

        # --- Step 2: Linux fallback: detect unmounted block device ---
        if system == "Linux":
            try:
                result = subprocess.run(
                    ["lsblk", "-o", "NAME,LABEL,MOUNTPOINT", "-P"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for line in result.stdout.splitlines():
                    fields = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
                    label_field = fields.get("LABEL", "").strip('"')
                    mount_field = fields.get("MOUNTPOINT", "").strip('"')
                    name_field = fields.get("NAME", "").strip('"')

                    if label_field.lower() == label.lower() and not mount_field:
                        device_path = f"/dev/{name_field}"
                        mount_point = f"/mnt/{label_field}"
                        os.makedirs(mount_point, exist_ok=True)
                        print(f"Mounting {device_path} -> {mount_point}")
                        subprocess.run(
                            ["sudo", "mount", device_path, mount_point], check=False
                        )
                        return mount_point
            except Exception as e:
                print("Linux mount fallback error:", e)

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
