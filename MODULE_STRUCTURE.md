# Pico Log Recorder - Module Structure

## Overview
The code has been split into modular files for better maintainability and future extensibility.

## File Structure

```
system-rpi_zero/
├── main.py                 # Entry point, orchestration, argument parsing
├── config.py              # Configuration constants and settings
├── serial_reader.py       # Serial connection & reading thread
├── log_manager.py         # File recording and session management
├── server_api.py          # Server communication (future implementation)
├── utils.py               # Helper functions (timestamp, port detection)
└── pico_log_recorder.py   # Legacy monolithic version (kept for reference)
```

## Module Responsibilities

### `main.py`
- **Entry point** for the application
- Parses command-line arguments
- Creates and coordinates all components
- Main event loop (reads from queue, prints, and writes to file)
- Handles graceful shutdown (Ctrl+C)

**Run with:**
```bash
python main.py --help
python main.py --platform windows
python main.py --port COM3 --baud 115200
```

### `config.py`
- All configuration constants in one place
- Serial settings (baud, timeouts, chunk sizes)
- Session markers and handshake messages
- File naming patterns and date formats
- Threading timeouts and queue sizes

**Easy to modify** settings without touching code logic.

### `serial_reader.py`
- `SerialReaderThread` class - runs in background thread
- Handles USB-CDC serial connection to Pico
- **Handshake protocol**: Sends `::RPI-ZERO-LOG::READY` until `::RPI-PICO-LOG::START` received
- Auto-reconnect with exponential backoff
- Line buffering and decoding (handles `\r\n`, partial lines)
- Puts decoded lines into thread-safe queue

### `log_manager.py`
- `FileRecorder` class - manages log file writing
- **Session-based logging**: `session-001.log`, `session-002.log`, etc.
- Date-based folder organization: `logs/DD-MM-YYYY/`
- Auto-detects and increments session numbers
- Handles session marker detection and file rolling
- Automatic date rollover at midnight

### `server_api.py`
- `ServerAPI` class - placeholder for future server communication
- **To be implemented:**
  - Upload log buffers to server
  - Send heartbeat signals
  - Report device status
  - Retry logic with exponential backoff

### `utils.py`
- `now_ts()` - Returns current timestamp in `DD-MM-YYYY HH:MM:SS` format
- `find_pico_port()` - Auto-detects Pico USB port
  - Matches by VID/PID, product name, manufacturer
  - Platform-aware sorting (COM ports on Windows, /dev/ttyACM on Linux)

## Usage

### Running the System

**Auto-detect port (recommended):**
```bash
python main.py
```

**Specify port explicitly:**
```bash
# Windows
python main.py --port COM3

# Linux/RPi
python main.py --port /dev/ttyACM0
```

**Custom settings:**
```bash
python main.py --baud 115200 --log-dir my_logs --platform windows
```

### Dependencies
- Python 3.7+
- `pyserial` (already in `env/`)

**Install in virtual environment:**
```bash
# Windows
env\Scripts\activate
pip install pyserial

# Linux/RPi
source env/bin/activate
pip install pyserial
```

## How It Works

### Thread Architecture
```
Main Thread
  ├─ Parse arguments
  ├─ Create FileRecorder
  ├─ Create SerialReaderThread
  ├─ Start reader thread
  └─ Loop: Read queue → Print → Write to file

SerialReaderThread (Background)
  ├─ Auto-detect/connect to Pico
  ├─ Perform handshake
  ├─ Read serial data
  ├─ Buffer and decode lines
  └─ Put lines in queue
```

### Handshake Protocol
1. **Zero boots** → Starts main.py
2. **SerialReaderThread** connects to Pico's USB port
3. **Zero sends** `::RPI-ZERO-LOG::READY` every 0.5s
4. **Pico responds** with `::RPI-PICO-LOG::START` (session marker)
5. **Zero creates** `logs/DD-MM-YYYY/session-001.log`
6. Normal logging begins

### Session Management
- **First marker** → Creates `session-001.log`
- **Subsequent markers** → Increments to `session-002.log`, `session-003.log`, etc.
- **Date changes** → New folder created, session resets to 001
- **Session numbering** auto-detects highest existing session on startup

### Auto-Reconnect
- If USB disconnects, thread keeps retrying
- Exponential backoff: 0.5s → 0.75s → 1.125s → ... → 5s (max)
- Handshake repeats on each reconnection

## Future Enhancements

### Planned Features (Not Yet Implemented)
1. **Dual Buffer System**
   - Keep 1-minute of data in memory buffers
   - Swap buffers every 60 seconds
   - Upload completed buffer to server in background
   - Reduces SD card wear, faster than disk writes

2. **Server Upload Thread**
   - Background thread uploads log buffers
   - Compress data (gzip) before sending
   - Retry failed uploads with exponential backoff
   - Queue pending uploads if network unavailable

3. **Heartbeat Thread**
   - Send device status every 30 seconds
   - Report: connection status, session info, queue size
   - Server can monitor if device is alive

4. **Configuration File**
   - Load settings from `config.yaml` or `config.json`
   - Override with command-line arguments
   - Store API keys, server URLs securely

## Migration from Legacy Version

The original `pico_log_recorder.py` is still available for reference.

**Differences:**
- Same functionality, just reorganized
- All features preserved (handshake, auto-reconnect, session management)
- Configuration values now in `config.py`
- Easier to extend with new features

**To switch back:**
```bash
python pico_log_recorder.py  # Old version
python main.py               # New modular version
```

## Development

### Adding New Features

**Example: Add server upload**
1. Implement methods in `server_api.py`
2. Add new thread in `main.py` that calls `ServerAPI.upload_log_buffer()`
3. Add upload configuration to `config.py`
4. No changes needed to serial reading or file management

**Example: Add heartbeat**
1. Implement `ServerAPI.send_heartbeat()` in `server_api.py`
2. Create `HeartbeatThread` in new file or `main.py`
3. Start thread in `main.run_threads()`

### Testing

**Test port detection:**
```bash
python -c "from utils import find_pico_port; print(find_pico_port(None, None, None, '', '', 'windows'))"
```

**Test with mock/real Pico:**
```bash
python main.py --port COM3  # Replace with your port
# Press Ctrl+C to stop
```

**Check logs:**
```bash
dir logs\17-10-2025  # Windows
ls logs/17-10-2025/  # Linux
```

## Troubleshooting

**Port not found:**
- Check USB cable connection
- Verify Pico is powered and running CDC serial code
- Try specifying `--port` manually
- Check with: `python -m serial.tools.list_ports`

**Session not incrementing:**
- Verify Pico is sending `::RPI-PICO-LOG::START` marker
- Check console output for "Session marker detected"
- Ensure handshake completes successfully

**Import errors:**
- Make sure all module files are in same directory
- Activate virtual environment: `env\Scripts\activate`
- Check Python path: `python -c "import sys; print(sys.path)"`

## License
Same as original project.
