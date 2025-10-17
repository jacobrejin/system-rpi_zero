"""
Log file management and coordination.
Handles session-based log files organized by date.
"""

import time
from pathlib import Path

from config import (
    DATE_FORMAT,
    SESSION_FILE_PATTERN,
    DATA_FILE_PATTERN,
    DATA_LINE_PREFIX,
)
from utils import now_ts


class FileRecorder:
    """
    Writes lines to disk under logs/DD-MM-YYYY/ directories.

    Features:
    - Session-based logging (session-001.log, session-002.log, ...)
    - Separate data file recording for lines starting with specified prefix
    - Auto-increments session number when marker is detected
    - Automatic date rollover creates new folders
    - Session numbering auto-detects highest existing session
    """

    def __init__(self, base_dir: Path, session_marker: str, data_dir: Path = None):
        """
        Initialize file recorder.

        Args:
            base_dir: Base directory for logs (e.g., 'logs/')
            session_marker: String that triggers new session creation
            data_dir: Base directory for data files (e.g., 'data/'). If None, data recording disabled.
        """
        self.base_dir = Path(base_dir)
        self.data_dir = Path(data_dir) if data_dir else None
        self.session_marker = session_marker
        self.cur_date = time.strftime(DATE_FORMAT)
        self.session_index = self._get_next_session_index()
        self.cur_file = None
        self.cur_data_file = None  # Separate file handle for data lines

    def _folder(self, is_data: bool = False) -> Path:
        """
        Get or create folder for current date.

        Args:
            is_data: If True, returns data folder; otherwise returns log folder
        """
        base = self.data_dir if is_data and self.data_dir else self.base_dir
        d = base / self.cur_date
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _get_next_session_index(self) -> int:
        """
        Find the highest existing session number and return next index.
        Checks both log and data folders to keep them synchronized.
        """
        session_numbers = []

        # Check log folder
        log_folder = self._folder(is_data=False)
        existing_log_sessions = list(log_folder.glob("session-*.log"))
        for f in existing_log_sessions:
            try:
                num_str = f.stem.replace("session-", "")
                session_numbers.append(int(num_str))
            except ValueError:
                continue

        # Check data folder if it exists
        if self.data_dir:
            data_folder = self._folder(is_data=True)
            existing_data_sessions = list(data_folder.glob("data-*.log"))
            for f in existing_data_sessions:
                try:
                    num_str = f.stem.replace("data-", "")
                    session_numbers.append(int(num_str))
                except ValueError:
                    continue

        if session_numbers:
            return max(session_numbers) + 1
        return 1

    def _roll_session(self):
        """Close current files and open new session files for both logs and data."""
        # Close and open log file
        if self.cur_file:
            self.cur_file.close()
        fname = SESSION_FILE_PATTERN.format(self.session_index)
        self.cur_file = open(
            self._folder(is_data=False) / fname, "a", encoding="utf-8", buffering=1
        )

        # Close and open data file if data directory is configured
        if self.data_dir:
            if self.cur_data_file:
                self.cur_data_file.close()
            data_fname = DATA_FILE_PATTERN.format(self.session_index)
            self.cur_data_file = open(
                self._folder(is_data=True) / data_fname,
                "a",
                encoding="utf-8",
                buffering=1,
            )

    def _maybe_roll_date(self):
        """Check if date has changed and roll to new date folder if needed."""
        today = time.strftime(DATE_FORMAT)
        if today != self.cur_date:
            # New date; create new session files
            if self.cur_file:
                self.cur_file.close()
            if self.cur_data_file:
                self.cur_data_file.close()
            self.cur_date = today
            self.session_index = self._get_next_session_index()
            self._roll_session()

    def write_line(self, line: str):
        """
        Write a line to the appropriate log file(s).

        - Lines starting with DATA_LINE_PREFIX go to both log and data files
        - Other lines go only to log file
        - If line contains session marker, rolls to new session files
        - Automatically handles date rollovers

        Args:
            line: Text line to write (without trailing newline)
        """
        self._maybe_roll_date()

        if self.session_marker and self.session_marker in line:
            # If a file is already open, increment to create a new session
            if self.cur_file is not None:
                self.session_index += 1
                print(
                    f"[{now_ts()}] Session marker detected, "
                    f"rolling to {SESSION_FILE_PATTERN.format(self.session_index)}",
                    flush=True,
                )
            else:
                print(
                    f"[{now_ts()}] First session marker detected, "
                    f"creating {SESSION_FILE_PATTERN.format(self.session_index)}",
                    flush=True,
                )
            self._roll_session()
        else:
            if self.cur_file is None:
                self._roll_session()

            # Write to log file
            self.cur_file.write(f"{line}\n")
            self.cur_file.flush()

            # If it's a data line, also write to data file
            if self.data_dir and line.startswith(DATA_LINE_PREFIX):
                if self.cur_data_file is None:
                    # Ensure data file is open (shouldn't happen if _roll_session works correctly)
                    data_fname = DATA_FILE_PATTERN.format(self.session_index)
                    self.cur_data_file = open(
                        self._folder(is_data=True) / data_fname,
                        "a",
                        encoding="utf-8",
                        buffering=1,
                    )
                self.cur_data_file.write(f"{line}\n")
                self.cur_data_file.flush()

    def close(self):
        """Close the current log and data files."""
        if self.cur_file:
            self.cur_file.close()
            self.cur_file = None
        if self.cur_data_file:
            self.cur_data_file.close()
            self.cur_data_file = None
