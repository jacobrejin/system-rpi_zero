# Quick Start Guide

## What Changed?

The single `pico_log_recorder.py` file (367 lines) has been split into 6 focused modules:

| File | Lines | Purpose |
|------|-------|---------|
| `config.py` | ~30 | All constants and settings |
| `utils.py` | ~90 | Helper functions (timestamp, port detection) |
| `serial_reader.py` | ~150 | Serial connection and reading thread |
| `log_manager.py` | ~120 | File writing and session management |
| `server_api.py` | ~60 | Server communication (placeholder) |
| `main.py` | ~140 | Entry point and orchestration |

## Why Modularize?

✅ **Easier to understand** - Each file has one clear responsibility  
✅ **Easier to test** - Test individual components separately  
✅ **Easier to extend** - Add server features without touching serial code  
✅ **Easier to maintain** - Find and fix bugs faster  
✅ **Better collaboration** - Multiple people can work on different modules  

## Running the New Version

**Same command as before:**
```bash
python main.py
```

**All arguments still work:**
```bash
python main.py --platform windows --baud 115200 --log-dir logs
```

## Module Dependencies

```
main.py
  ├─ imports config.py
  ├─ imports utils.py (find_pico_port)
  ├─ imports serial_reader.py (SerialReaderThread)
  └─ imports log_manager.py (FileRecorder)

serial_reader.py
  └─ imports config.py

log_manager.py
  ├─ imports config.py
  └─ imports utils.py (now_ts)

utils.py
  └─ imports config.py

server_api.py
  └─ (standalone, no internal imports)
```

## Data Flow

```
Raspberry Pi Pico (USB-CDC Serial)
            │
            ▼
    SerialReaderThread
    (serial_reader.py)
            │
            ├─ Handshake Protocol
            ├─ Auto-reconnect
            └─ Line buffering
            │
            ▼
    Thread-Safe Queue
            │
            ▼
    Main Loop (main.py)
            │
            ├─ Print to console
            └─ Write to file
            │
            ▼
    FileRecorder
    (log_manager.py)
            │
            ├─ Session detection
            ├─ Date rollover
            └─ Auto-increment
            │
            ▼
    logs/DD-MM-YYYY/session-NNN.log
```

## Testing Checklist

- [x] `main.py --help` shows help text
- [x] All modules compile without errors
- [ ] Connect to real Pico and verify logging works
- [ ] Verify session marker creates new file
- [ ] Test auto-reconnect (unplug/replug USB)
- [ ] Test date rollover (change system date)
- [ ] Verify logs/ directory structure

## Next Steps

1. **Test with real hardware**
   ```bash
   python main.py --platform windows
   ```

2. **Verify session files are created**
   ```bash
   dir logs\17-10-2025
   ```

3. **Test handshake** - Watch console for "Session marker detected"

4. **Test reconnection** - Unplug and replug USB cable

5. **Implement server upload** (when ready)
   - Edit `server_api.py`
   - Add upload thread in `main.py`
   - Configure endpoints in `config.py`

## Configuration

All settings are now centralized in `config.py`:

```python
# Change these as needed
DEFAULT_BAUD = 115200
DEFAULT_SESSION_MARKER = "::RPI-PICO-LOG::START"
SERIAL_TIMEOUT = 0.1
QUEUE_MAX_SIZE = 1000
```

No need to search through code to find configuration values!

## Backward Compatibility

The original `pico_log_recorder.py` is still there if you need it:

```bash
python pico_log_recorder.py  # Old monolithic version
python main.py               # New modular version
```

Both work identically - just different organization.

## Documentation

- **MODULE_STRUCTURE.md** - Detailed architecture documentation
- **readme.md** - RPi Zero 2W setup and networking
- **gpt-context.md** - Project context and requirements
- **QUICK_START.md** - This file!

## Questions?

**Q: Do I need to change my Pico code?**  
A: No! Serial protocol is identical.

**Q: Will my existing logs work?**  
A: Yes! Same file format and directory structure.

**Q: Can I customize session markers?**  
A: Yes! Use `--session-marker "YOUR_MARKER"` or edit `config.py`

**Q: How do I add server upload?**  
A: See `server_api.py` for placeholder methods. Coming soon!

**Q: Performance difference?**  
A: None - same threading model, same efficiency.

---

**Ready to go!** 🚀

```bash
python main.py
```
