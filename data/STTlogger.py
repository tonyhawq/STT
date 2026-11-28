import io
from datetime import datetime
from pathlib import Path
import threading

class SimpleSTTLogger:
    def __init__(self, files: str | list[str], *, persist: bool = False):
        filenames = files
        if isinstance(files, str):
            filenames = [files]
        self.files: list[io.TextIOWrapper] = []
        for name in filenames: 
            Path(name).parent.mkdir(parents=True, exist_ok=True)
            self.files.append(open(name, "a" if persist else "w"))
        self.lock = threading.RLock()

    def close(self):
        for file in self.files:
            file.close()

    def flush(self):
        for file in self.files:
            file.flush()

    def log(self, message: str, *, source: str | None = None):
        self.logFast(message, source=source)
        for file in self.files:
            file.flush()
    
    def logFast(self, message: str, *, source: str | None = None):
        with self.lock:
            if source:
                created = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ({source}) {message}\n"
            else:
                created = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}\n"
            for file in self.files:
                file.write(created)

