#!/usr/bin/env bash
set -euo pipefail

# setup_tmux_systemd.sh
# Usage: sudo ./setup_tmux_systemd.sh [--app-dir DIR] [--user USER] [--service-name NAME] [--venv PATH]
# Automates creation of run.sh, systemd unit for running the project inside a tmux session.

APP_DIR="/home/rejin/system-rpi_zero"
USER_NAME="rejin"
SERVICE_NAME="pico-agent"
TMUX_SOCKET="pico-ag"
VENV_PY="${APP_DIR}/env/bin/python"
RUN_SH_PATH="${APP_DIR}/run.sh"

print_usage() {
  cat <<EOF
Usage: sudo $0 [--app-dir DIR] [--user NAME] [--service-name NAME] [--venv PATH]

Options:
  --app-dir DIR       Application directory (default: ${APP_DIR})
  --user NAME         System user to run the service as (default: ${USER_NAME})
  --service-name NAME systemd service name (default: ${SERVICE_NAME})
  --venv PATH         Full path to python inside virtualenv (default: ${VENV_PY})
  -h, --help          Show this help
EOF
}

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --app-dir) APP_DIR="$2"; shift 2;;
    --user) USER_NAME="$2"; shift 2;;
    --service-name) SERVICE_NAME="$2"; shift 2;;
    --venv) VENV_PY="$2"; shift 2;;
    -h|--help) print_usage; exit 0;;
    *) echo "Unknown arg: $1"; print_usage; exit 2;;
  esac
done

RUN_SH_PATH="${APP_DIR}/run.sh"

echo "Using settings:
  APP_DIR=${APP_DIR}
  USER=${USER_NAME}
  SERVICE=${SERVICE_NAME}
  TMUX_SOCKET=${TMUX_SOCKET}
  VENV_PY=${VENV_PY}
  RUN_SH=${RUN_SH_PATH}
"

if [[ $(id -u) -ne 0 ]]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

# Create application directory if it doesn't exist
if [[ ! -d "${APP_DIR}" ]]; then
  echo "Creating application directory: ${APP_DIR}"
  mkdir -p "${APP_DIR}"
  chown ${USER_NAME}:${USER_NAME} "${APP_DIR}" || true
fi

echo "Writing run.sh to ${RUN_SH_PATH}"
cat > "${RUN_SH_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

cd "${APP_DIR}"

# Use the provided virtualenv python if present, else fallback to system python
if [[ -x "${VENV_PY}" ]]; then
  exec "${VENV_PY}" -u main.py
else
  exec python3 -u main.py
fi
EOF

chmod 0755 "${RUN_SH_PATH}"
chown ${USER_NAME}:${USER_NAME} "${RUN_SH_PATH}" || true

UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
echo "Writing systemd unit to ${UNIT_PATH}"
cat > "${UNIT_PATH}" <<EOF
[Unit]
Description=${SERVICE_NAME} (tmux session at boot)
After=network-online.target
Wants=network-online.target
ConditionPathExists=${APP_DIR}

[Service]
Type=oneshot
RemainAfterExit=yes
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${APP_DIR}
Environment=HOME=/home/${USER_NAME}

# Ensure a dedicated tmux server socket; ignore if it already exists
ExecStart=/bin/sh -lc '/usr/bin/tmux -L ${TMUX_SOCKET} start-server || true'
# Reuse session if present, else create and run your app
ExecStart=/bin/sh -lc '/usr/bin/tmux -L ${TMUX_SOCKET} has-session -t ${SERVICE_NAME} 2>/dev/null || /usr/bin/tmux -L ${TMUX_SOCKET} new-session -d -s ${SERVICE_NAME} "${RUN_SH_PATH}"'

# Clean stop
ExecStop=/bin/sh -lc '/usr/bin/tmux -L ${TMUX_SOCKET} kill-session -t ${SERVICE_NAME} 2>/dev/null || true'

Restart=no

[Install]
WantedBy=multi-user.target
EOF

echo "Installing tmux and reloading systemd"
apt update -y || true
apt install -y tmux

systemctl daemon-reload
systemctl enable --now ${SERVICE_NAME}.service

echo "Done. You can attach to the tmux session using:
  tmux -L ${TMUX_SOCKET} attach -t ${SERVICE_NAME}
Or list sessions:
  tmux -L ${TMUX_SOCKET} ls
To restart the service after updates:
  systemctl restart ${SERVICE_NAME}.service
"

exit 0
