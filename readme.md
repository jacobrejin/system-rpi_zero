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

# Using the Auto-Setup Script

1 - Copy to your Pi and run as root
chmod +x setup_pi_wifi_rpi_connect.sh
sudo ./setup_pi_wifi_rpi_connect.sh

2 - When it shows your MAC, go register it at:
   https://resnet.apps.cranfield.ac.uk/
   (Add new PSK -> paste MAC -> copy generated PSK)

3 - Paste the PSK into the script when prompted.
4 - It’ll bring up “Cranfield IOT”, keep “preconfigured” as fallback (if present),
   and guide you through rpi-connect signin.