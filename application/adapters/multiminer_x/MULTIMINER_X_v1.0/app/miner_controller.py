from __future__ import annotations
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


class MinerController:
    def __init__(self, event_queue: queue.Queue):
        self.events = event_queue
        self.processes: dict[str, subprocess.Popen] = {}
        self.readers: dict[str, threading.Thread] = {}
        self.lock = threading.RLock()

    def _reader(self, name: str, proc: subprocess.Popen):
        log_path = LOG_DIR / f"{name.lower()}.log"
        try:
            with log_path.open("a", encoding="utf-8", errors="replace") as fp:
                fp.write(f"\n--- START {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                while True:
                    line = proc.stdout.readline() if proc.stdout else ""
                    if not line:
                        break
                    line = line.rstrip("\r\n")
                    fp.write(line + "\n")
                    fp.flush()
                    self.events.put(("log", name, line))
        except Exception as exc:
            self.events.put(("log", name, f"Log reader error: {exc}"))
        finally:
            code = proc.poll()
            self.events.put(("exit", name, code))
            with self.lock:
                if self.processes.get(name) is proc:
                    self.processes.pop(name, None)

    def start(self, name: str, exe: Path, args: list[str]):
        with self.lock:
            old = self.processes.get(name)
            if old and old.poll() is None:
                raise RuntimeError(f"{name} rulează deja.")
            if not exe.is_file():
                raise FileNotFoundError(f"Nu găsesc {exe}. Rulează INSTALL_BACKENDS.ps1.")
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(
                [str(exe), *args], cwd=str(exe.parent),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, creationflags=creationflags
            )
            self.processes[name] = proc
            t = threading.Thread(target=self._reader, args=(name, proc), daemon=True)
            self.readers[name] = t
            t.start()
            self.events.put(("state", name, f"Pornit PID {proc.pid}"))

    def stop(self, name: str, timeout: float = 7.0):
        with self.lock:
            proc = self.processes.get(name)
        if not proc or proc.poll() is not None:
            self.events.put(("state", name, "Oprit"))
            return
        self.events.put(("state", name, "Se oprește..."))
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        self.events.put(("state", name, "Oprit"))

    def stop_all(self):
        for name in ("GPU", "CPU"):
            self.stop(name)

    def status(self, name: str) -> bool:
        with self.lock:
            proc = self.processes.get(name)
            return bool(proc and proc.poll() is None)
