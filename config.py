"""
Configuration constants and settings for the Pico Log Recorder system.
"""

# Serial Communication
DEFAULT_BAUD = 115200

# Session Markers
DEFAULT_SESSION_MARKER = "::RPI-PICO-LOG::START"
READY_MESSAGE = "::RPI-ZERO-LOG::READY"

# Connection Settings
SERIAL_TIMEOUT = 0.1  # seconds
SERIAL_READ_CHUNK_SIZE = 1024  # bytes
INITIAL_BACKOFF = 0.5  # seconds
MAX_BACKOFF = 5.0  # seconds
RECONNECT_RETRY_INTERVAL = 0.5  # seconds

# Handshake Settings
HANDSHAKE_SEND_INTERVAL = 0.5  # seconds - how often to send READY message

# Queue Settings
QUEUE_MAX_SIZE = 1000
QUEUE_TIMEOUT = 0.5  # seconds

# File Settings
DEFAULT_LOG_DIR = "logs"
DEFAULT_DATA_DIR = "data"  # Separate directory for data lines (lines starting with 'D')
DATE_FORMAT = "%d-%m-%Y"
TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M:%S"
SESSION_FILE_PATTERN = "session-{:03d}.log"
DATA_FILE_PATTERN = "data-{:03d}.log"  # Pattern for data files
DATA_LINE_PREFIX = "D"  # Prefix that identifies data lines

# Threading
THREAD_JOIN_TIMEOUT = 2.0  # seconds
