#!/usr/bin/env bash
# RPi Zero 2W quick-setup: Cranfield IoT Wi‑Fi + RPi Connect (persistent)
#
# This script performs a minimal, opinionated setup on a Raspberry Pi OS Lite
# system to install and configure NetworkManager, enable the Wi‑Fi radio,
# optionally install and sign in to RPi Connect (rpi-connect-lite), and create
# a persistent connection profile for the 'Cranfield IOT' SSID using a PSK
# obtained from the Cranfield IoT portal.
#
# Usage: run as root (recommended) or with sudo:
#   sudo bash setup_pi_wifi_rpi_connect.sh

# Fail fast on errors, treat unset variables as errors, and ensure pipelines
# fail when any command fails in the pipeline.
set -euo pipefail

# --- Logging setup ---------------------------------------------------------
# Create a timestamped logfile in /var/log when possible, otherwise fall
# back to the script directory. All stdout/stderr from the script will be
# tee'd to this logfile so the user can inspect it later if connectivity
# is lost or for debugging.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}"
LOGFILE_NAME="setup_pi_wifi_rpi_connect-$(date +%Y%m%d-%H%M%S).log"
LOGFILE_PATH="${LOG_DIR}/${LOGFILE_NAME}"

# Open a file descriptor that tees stdout+stderr to the logfile while
# preserving interactive stdin. We redirect both stdout and stderr into
# tee so the logfile contains everything the user saw in the terminal.
exec > >(tee -a "${LOGFILE_PATH}") 2>&1

# Print a header so logs are easier to parse later
echo "--- setup_pi_wifi_rpi_connect.sh log started: $(date -u +'%Y-%m-%dT%H:%M:%SZ') ---"
echo "Logfile: ${LOGFILE_PATH}"
echo

# Terminal color codes for prettier output messages
RED='\033[0;31m'; GREEN='\033[0;32m'; YEL='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

# Small helpers for consistent output formatting
# - say: informational message
# - ok: success message
# - warn: non-fatal warning
# - die: print error and exit non-zero
say() { echo -e "${CYAN}[setup]${NC} $*"; }
ok()  { echo -e "${GREEN}[ok]${NC} $*"; }
warn(){ echo -e "${YEL}[warn]${NC} $*"; }
die(){ echo -e "${RED}[error]${NC} $*"; exit 1; }

# Ensure the script is running as root; many operations (apt, systemctl) need it
require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Please run as root: sudo bash $0"
  fi
}

# Check whether a command exists in PATH
check_cmd() { command -v "$1" >/dev/null 2>&1; }

# Simple pause used after prompting the user (keeps the script interactive)
press_enter() { read -rp "Press [Enter] to continue..."; }

### ---------- Begin ----------
require_root

# Update package lists to ensure we have the latest package metadata
say "Updating package lists..."
apt-get update -y

# Install the minimal packages we rely on. We ignore failures from apt here
# for non-critical packages to avoid aborting in environments where some
# packages may be unavailable (but we still continue trying to configure
# NetworkManager and the Wi‑Fi connection).
say "Installing required packages: network-manager, dbus, ca-certificates, iperf3, speedtest-cli"
apt-get install -y network-manager dbus ca-certificates iperf3 speedtest-cli || true

# Try to install the lightweight rpi-connect package which provides the
# 'rpi-connect' CLI. If the install fails we continue but print a helpful
# warning so the user can install it manually later.
say "Installing RPi Connect (Lite)"
if ! check_cmd rpi-connect; then
  apt-get install -y rpi-connect-lite || warn "rpi-connect-lite install skipped/failed; you can install later with: sudo apt install rpi-connect-lite"
fi

# NetworkManager is preferred here; disable dhcpcd if present and ensure the
# NetworkManager service is enabled and running so nmcli is available.
say "Enabling NetworkManager (disabling dhcpcd if present)"
systemctl disable --now dhcpcd 2>/dev/null || true
systemctl enable --now NetworkManager
systemctl start NetworkManager || true

# Configure rpi-connect for persistent sign-in. Enables linger so the user's
# background agent can continue running after logout (useful for desktop
# sessions or service tokens). This section is skipped if rpi-connect is not
# available.
say "Configuring persistent RPi Connect sign-in"
if check_cmd rpi-connect; then
  # Turn the service on (best-effort)
  rpi-connect on || true
  # If not already signed in, start the interactive signin flow which may
  # present a URL for the user to open in a browser to authorise the device.
  # The `whoami` subcommand isn't available; use `rpi-connect status` and
  # look for a line like: "signed in: yes" (case-insensitive).
  if ! rpi-connect status 2>/dev/null | grep -iq '^signed in:[[:space:]]*yes'; then
    say "Starting sign-in flow (follow the URL shown)"
    rpi-connect signin || warn "rpi-connect signin skipped/failed; run manually later."
  else
    ok "RPi Connect already signed in."
  fi
  # Use the invoking user if available; enable lingering for that user so the
  # rpi-connect background helper can persist beyond interactive sessions.
  SUDO_USER_REAL="${SUDO_USER:-$(logname)}"
  sudo loginctl enable-linger "$SUDO_USER_REAL" || warn "Could not enable linger for $SUDO_USER_REAL"
else
  warn "rpi-connect not installed. Install later with: sudo apt install rpi-connect-lite"
fi

# Ensure the wireless radio isn't soft-blocked (rfkill is a no-op on some
# systems, so ignore failures).
say "Ensuring Wi‑Fi radio is enabled"
rfkill unblock wifi || true

# Require nmcli from NetworkManager for the rest of the script; exit if it's
# not present because we cannot proceed with creating a connection profile.
say "Verifying nmcli availability"
check_cmd nmcli || die "nmcli not found. Ensure network-manager installed correctly."

# Attempt to determine the WLAN hardware MAC address for wlan0. This value
# is used when registering the device with the Cranfield IoT portal to obtain
# a PSK tied to the device MAC.
say "Determining WLAN MAC address"
MAC="$(nmcli device show wlan0 2>/dev/null | awk '/HWADDR/ {print $2}')"
if [[ -z "${MAC}" ]]; then
  # Fallback to reading /sys/class/net if nmcli didn't return the MAC
  MAC="$(cat /sys/class/net/wlan0/address 2>/dev/null || true)"
fi
[[ -n "${MAC}" ]] || die "Could not determine wlan0 MAC address."
echo -e "${YEL}Your Pi's Wi‑Fi MAC (wlan0): ${GREEN}${MAC}${NC}"

# Prompt the user to register the device on the Cranfield portal and obtain a
# pre-shared key (PSK). This is an interactive step and requires the user to
# copy the generated PSK into this script when prompted.
cat <<'TIP'

Go to the Cranfield IoT portal and register your device:
  https://resnet.apps.cranfield.ac.uk/
Click “Add new PSK”, enter the MAC shown above, and copy the generated PSK.

TIP
press_enter

# Default SSID for the Cranfield IOT network; allow the user to override it.
SSID_DEFAULT="Cranfield IOT"
read -rp "Enter IOT SSID [${SSID_DEFAULT}]: " SSID
SSID="${SSID:-$SSID_DEFAULT}"

# Read the PSK from user input (paste from the portal). Fail if empty.
read -rp "Paste the IOT PSK (from the portal): " PSK
[[ -n "${PSK}" ]] || die "PSK cannot be empty."

# Connection name and priority used for the nmcli profile we create
IOT_CONN_NAME="cranfield-iot"
IOT_PRIORITY=100

# Remove any old connection with the same name to avoid conflicts
say "Removing any previous '${IOT_CONN_NAME}' connection"
nmcli connection delete "${IOT_CONN_NAME}" 2>/dev/null || true

# Create a new Wi‑Fi connection profile for wlan0 using the provided SSID
# and PSK. Then set autoconnect and a priority so it will be preferred.
say "Creating IoT connection '${IOT_CONN_NAME}' for SSID '${SSID}'"
nmcli connection add type wifi ifname wlan0 con-name "${IOT_CONN_NAME}" ssid "${SSID}"
nmcli connection modify "${IOT_CONN_NAME}"   wifi-sec.key-mgmt wpa-psk   wifi-sec.psk "${PSK}"   connection.autoconnect yes   connection.autoconnect-priority ${IOT_PRIORITY}

# Try to bring the connection up immediately and rescan nearby Wi‑Fi first
say "Connecting to '${IOT_CONN_NAME}'"
nmcli device wifi rescan || true
nmcli connection up "${IOT_CONN_NAME}" || warn "Failed to connect to ${IOT_CONN_NAME}"

# Basic connectivity test: ping a well-known public DNS server and report
# whether the internet is reachable. This is a simple heuristic only.
say "Testing connectivity"
if ping -c 2 -W 2 8.8.8.8 >/dev/null 2>&1; then
  ok "Internet reachable"
else
  warn "No internet connectivity. Check PSK or Wi-Fi coverage."
fi

ok "Setup complete. RPi Connect will auto-start on boot."
echo -e "${YEL}Tip:${NC} Reboot to validate autoconnect: sudo reboot"
