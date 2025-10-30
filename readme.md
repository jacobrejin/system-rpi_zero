# RPI ZERo 2W Setup

## OS Installation Steps:
1. Flash a Raspbian Server OS image to the SD card using [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
**Raspberry Pi OS Lite(64 bit) A port of Debian Trixie with no Desktop Environment**
2. Mak esure to setup a temporary wifi credential in the imager settings. (This could be an hotspot from the phone)
3. Also make sure to enable SSH in the imager settings, and add the pi username and hostname for ease of connection later.
4. Insert the SD card into the RPI Zero 2W and power it on.

---
<br>

## Connecting to the RPI via SSH
1. Find the IP address of the PI Zero. You can use angry IP scanner to find the IP address of the RPI on the network. [angry IP scanner](https://angryip.org/download/#windows)
2. Use an SSH client like [PuTTY](https://www.putty.org/) to connect to the RPI using the IP address found in the previous step.
3. Login with the username and password set in the imager settings.

## Setting up remote SSH access over the internet
1. We are going to use the Rpi-Connect service to setup remote SSH access over the internet. This will allow us to connect to the RPI from anywhere in the world.
2. Follow the instructions on the [Rpi-Connect Page](https://www.raspberrypi.com/software/connect/).
3. To setup the Rpi-Connect service on the RPI Zero 2W read the following guide [here](https://www.raspberrypi.com/documentation/services/connect.html)
4. Install `sudo apt install rpi-connect-lite`
5. Turn on `rpi-connect on`
6. Sign In `rpi-connect signin`
7. You should get a URL to visit to complete the signin process. `Complete sign in by visiting https://connect.raspberrypi.com/verify/XXXX-XXXX`

After signing in, you should be able to see your RPI Zero 2W on the Rpi-Connect dashboard. Now you can open a SSH session to the RPI from anywhere in the world using the Rpi-Connect service.

---
<br>

## Setting up Wifi to connect to the School Network (Eduroam)

This guide documents how to connect a **Raspberry Pi Zero 2W (Lite, headless)** to Cranfield University Wi‑Fi  **Cranfield IoT** — for reliable Internet and remote SSH access. (The desktop version on rpi os can connect to eduroam directly via the GUI, but the headless version does not meet the security requirements.)

1. Find MAC address:
   ```bash
   nmcli device show wlan0 | grep HWADDR
   ```
2. Go to [https://resnet.apps.cranfield.ac.uk/](https://resnet.apps.cranfield.ac.uk/), add a new PSK for that MAC, and copy the generated password.
3. Create the IoT connection:
   ```bash
   sudo nmcli connection add type wifi ifname wlan0 con-name cranfield-iot ssid "Cranfield IOT"
   sudo nmcli connection modify cranfield-iot wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YOUR_PSK"
   sudo nmcli connection modify cranfield-iot connection.autoconnect yes connection.autoconnect-priority 100
   sudo nmcli connection up cranfield-iot
   ```
4. Verify Internet access:
   ```bash
   ping -c4 8.8.8.8
   ping -c4 www.google.com
   ```

---
<br>

### Set fallback to temporary Wi‑Fi
If you keep a backup network (e.g. *preconfigured*):
```bash
sudo nmcli connection modify preconfigured connection.autoconnect yes
sudo nmcli connection modify preconfigured connection.autoconnect-priority 80
```
NetworkManager will prefer **Cranfield IOT**, but fall back to **preconfigured** if IOT is unavailable.

Check autoconnect status:
```bash
nmcli -f NAME,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show
```


---
<br>
<br>

#### ✅ Summary
| Task | Command |
|------|----------|
| List Wi‑Fi networks | `nmcli device wifi list` |
| Show active connection | `nmcli connection show --active` |
| Verify IP | `ip addr show wlan0` |
| Logs for Wi‑Fi | `journalctl -u NetworkManager -b | tail -n 50` |
| Test connectivity | `ping -c4 8.8.8.8` |

<br>
<br>

# Using the Auto-Setup Script

The above steps are automated in the script `setup_pi_wifi_rpi_connect.sh` included in this repository.

1 - Copy to your Pi and run as root
chmod +x setup_pi_wifi_rpi_connect.sh
sudo ./setup_pi_wifi_rpi_connect.sh

2 - When it shows your MAC, go register it at:
   https://resnet.apps.cranfield.ac.uk/
   (Add new PSK -> paste MAC -> copy generated PSK)

3 - Paste the PSK into the script when prompted.
4 - It’ll bring up “Cranfield IOT”, keep “preconfigured” as fallback (if present),
   and guide you through rpi-connect signin.

---

<br>
<br>

# Cloning and running a private GitHub repository on the Pi

You can clone a private GitHub repository to your Raspberry Pi Zero 2W using a Personal Access Token (PAT). The PAT method is the safest option for automation and scripts.

1) Generate a Personal Access Token (once, on your main computer)

- Go to https://github.com/settings/tokens
- Click "Generate new token → Fine-grained token"
- Give it repo read permissions and copy the token (it looks like `ghp_xxxxxxxxx...`).Sometimes called the Content Access Token Permission

2) Clone the private repository (quick but embed-token method)

On the Pi, replace <USER>, <TOKEN> and <REPO> with your values:

```
cd ~
git clone https://<USER>:<TOKEN>@github.com/<USER>/<REPO>.git
```

Example:

```
git clone https://myusername:ghp_abcd1234efgh5678ijkl9012mnop3456qrst@github.com/myusername/rpi-zero-project.git
```

Tip: Use single quotes around the URL if your token contains special characters.

3) Safer: use an environment variable for the token

Set the token in your shell (this avoids leaving the token in shell history for some shells):

```
export GITHUB_TOKEN="ghp_abcd1234efgh5678ijkl9012mnop3456qrst"
git clone https://$GITHUB_TOKEN@github.com/<USER>/<REPO>.git
```

On Debian-based systems you can add the export to `~/.profile` or a dedicated `~/.bashrc_local` file, but be careful with file permissions (see security notes below).


Change into the repository directory
```
cd <REPO>
```

Install Pip3 using apt
```
sudo apt update
sudo apt install python3-pip
```

Install the virtualenv package (using apt, as latest pi version does not allow pip install virtualenv):
```
sudo apt install python3-virtualenv
```
Create a virtual environment (optional but recommended):
```
virtualenv env
```

activate a virtual environment (optional but recommended):
```
source env/bin/activate
```

Install the required dependencies (if any):
```
pip3 install -r requirements.txt
```

4) Run the project on the Pi

```
python3 main.py
```


## Running as a background service (tmux + systemd)

Below are example files and commands to run the project in a detached tmux session at boot using systemd. Update paths and usernames if your setup differs.

### Assumptions (change these to match your setup)

- App folder: /home/rejin/system-rpi_zero
- Virtualenv: /home/rejin/system-rpi_zero/.venv
- Entry script: main.py
- Run as user: rejin
- tmux session name: pico-agent

### Tiny run script (uses your venv)

- Create: `/home/rejin/system-rpi_zero/run.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /home/rejin/system-rpi_zero

# Use your project’s virtualenv Python
exec /home/rejin/system-rpi_zero/env/bin/python -u main.py
```

- Make it executable:

```bash
chmod 775 /home/rejin/system-rpi_zero/run.sh
```

### systemd unit (starts a tmux session at boot)

Create: `/etc/systemd/system/pico-agent.service`

```ini
[Unit]
Description=Pico Agent (tmux session at boot)
After=network-online.target
Wants=network-online.target
ConditionPathExists=/home/rejin/system-rpi_zero

[Service]
Type=oneshot
RemainAfterExit=yes
User=rejin
Group=rejin
WorkingDirectory=/home/rejin/system-rpi_zero
Environment=HOME=/home/rejin

# Ensure a dedicated tmux server socket; ignore if it already exists
ExecStart=/bin/sh -lc '/usr/bin/tmux -L pico-ag start-server || true'
# Reuse session if present, else create and run your app
ExecStart=/bin/sh -lc '/usr/bin/tmux -L pico-ag has-session -t pico-agent 2>/dev/null || /usr/bin/tmux -L pico-ag new-session -d -s pico-agent "/home/rejin/system-rpi_zero/run.sh"'

# Clean stop
ExecStop=/bin/sh -lc '/usr/bin/tmux -L pico-ag kill-session -t pico-agent 2>/dev/null || true'

Restart=no

[Install]
WantedBy=multi-user.target

```

### Enable and start:

```bash
sudo apt update
sudo apt install -y tmux
sudo systemctl daemon-reload
sudo systemctl enable --now pico-agent.service
```

### Using it

Check if the Tmux has any sessions:
```bash
tmux -L pico-ag ls
```


Attach to the live console later:

```bash
tmux -L pico-ag attach -t pico-agent
```

Detach without stopping (leave it running): `Ctrl + B` (release), then D


Check service health:

```bash
systemctl status pico-agent.service
```


Restart if you update code:

```bash
sudo systemctl restart pico-agent.service
```

## Automated setup script (tmux + systemd)

A convenience script is included to automate creating `run.sh`, the systemd unit and enabling the service.

File: `scripts/setup_tmux_systemd.sh`

Summary: run this on the Pi (as root) to create the `run.sh` launcher, install `tmux`, write `/etc/systemd/system/<service>.service`, reload systemd and enable/start the service.

Usage example (run on the Pi in the project folder):

```bash
cd /home/rejin/system-rpi_zero
sudo ./scripts/setup_tmux_systemd.sh \
   --app-dir /home/rejin/system-rpi_zero \
   --user rejin \
   --service-name pico-agent \
   --venv /home/rejin/system-rpi_zero/env/bin/python
```

Notes:
- The script defaults match the example unit above: app dir `/home/rejin/system-rpi_zero`, user `rejin`, service name `pico-agent` and venv python at `env/bin/python`.
- The script must be run as root (use `sudo`) because it writes to `/etc/systemd/system` and installs packages.
- `run.sh` is created with executable permissions and will use the provided venv python if present, otherwise `python3`.

How to attach to the running console after install:

```bash
tmux -L pico-ag attach -t pico-agent
```

List sessions:

```bash
tmux -L pico-ag ls
```

Restart after updating code:

```bash
sudo systemctl restart pico-agent.service
```

## Firmware upload (Pico UF2)

A short note on how to upload firmware (.uf2) to a Raspberry Pi Pico from this project.

- Place the .uf2 file(s) you want to flash into the project `upload_binary/` folder (repo root).
- The running agent (the serial reader in this project) can perform the upload automatically: it sends an `UPLOAD` command to the Pico, closes the serial port and opens it at 1200 baud to trigger the RP2040 UF2 bootloader. The agent then waits for the mass-storage drive (typically labelled `RPI-RP2`) to appear and copies any `*.uf2` files from `upload_binary/` to the Pico.
- If the automatic upload fails or you prefer to do it manually, the helper script `test.py` can trigger the bootloader and copy files. Example (replace `COM5` with your port on Windows or `/dev/ttyACM0` on Linux):

```bash
python test.py --serial COM5
```

- Troubleshooting tips:
   - Ensure your `.uf2` file is present in `upload_binary/` before triggering an upload.
   - On Windows the Pico drive usually shows up with label `RPI-RP2`; on Linux it is usually mounted under `/media` or `/run/media`.
   - If the drive doesn't appear immediately, wait a few seconds and retry the trigger/copy.

This workflow avoids manual unplugging: opening the serial port at 1200 baud signals the Pico to reboot into UF2 bootloader mode, after which the OS exposes the Pico as a removable drive and copying the `.uf2` installs the new firmware.
