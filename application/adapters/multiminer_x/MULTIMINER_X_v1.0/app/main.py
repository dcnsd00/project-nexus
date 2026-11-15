from __future__ import annotations
import json
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from app.miner_controller import MinerController, ROOT, LOG_DIR
from core.mining_math import (probability_at_least_one_block, expected_blocks,
                              expected_wait_seconds, monte_carlo_block_probability,
                              energy_kwh, electricity_cost, split_cpu_threads)
from core.optimizer import cpu_thread_plan
from core.algorithm_registry import PAYOUT_ASSET_CANDIDATES, PROFILES, get_profile, format_payout_identity

CONFIG_PATH = ROOT / "config" / "settings.json"
CONFIG_PATH.parent.mkdir(exist_ok=True)
DEFAULTS = {
    "account_identity": "",
    "worker_name": "TUF1650",
    "payout_label": "BONK",
    "cpu_percent": 50,
    "gpu_intensity": 16,
    "gpu_stop_temp": 78,
    "auto_stop_temp": True,
}


def read_settings():
    data = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for key in DEFAULTS:
                    if key in saved:
                        data[key] = saved[key]
                if not re.fullmatch(r"[A-Za-z0-9]{2,12}", str(data.get("payout_label", ""))):
                    data["payout_label"] = "BONK"
        except Exception:
            pass
    return data


def write_settings(data):
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def app_resource(name: str) -> Path:
    return ROOT / "miners" / name


def locate_exe(folder: Path, exe_name: str) -> Path:
    direct = folder / exe_name
    if direct.exists():
        return direct
    candidates = list(folder.rglob(exe_name))
    return candidates[0] if candidates else direct


def validate_identity(identity: str, worker: str) -> str:
    identity = identity.strip()
    worker = worker.strip()
    if not identity:
        raise ValueError("Introdu alias-ul contului unMineable sau formatul legacy COIN:ADRESĂ.")
    if not worker or not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", worker):
        raise ValueError("Numele workerului trebuie să conțină doar litere, cifre, punct, _ sau - (max. 32).")
    if not re.fullmatch(r"[A-Za-z0-9:._-]+", identity):
        raise ValueError("Aliasul/adresa poate conține doar litere, cifre, :, punct, _ și -.")
    if len(identity) > 220:
        raise ValueError("Aliasul/adresa este prea lung(ă).")
    if ":" in identity:
        return f"{identity}.{worker}"
    return f"{identity}.{worker}"


class MinerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MULTIMINER X 1.1 — Multi-Asset Mining + Crypto Lab")
        self.geometry("1040x760")
        self.minsize(900, 680)
        self.configure(bg="#101820")
        self.settings = read_settings()
        self.events = queue.Queue()
        self.controller = MinerController(self.events)
        self._monitor_running = False
        self._build_style()
        self._build_ui()
        self.after(200, self._drain_events)
        self.after(2500, self._poll_gpu_telemetry)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#101820")
        style.configure("Panel.TFrame", background="#182632")
        style.configure("TLabel", background="#101820", foreground="#e8f0f5", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#ffffff")
        style.configure("Sub.TLabel", foreground="#a9bdca", font=("Segoe UI", 9))
        style.configure("PanelTitle.TLabel", background="#182632", foreground="#ffffff", font=("Segoe UI", 11, "bold"))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Accent.TButton", background="#1f8a70", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#26a785")])
        style.configure("Stop.TButton", background="#a63a50", foreground="#ffffff")
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=5)

    def _panel(self, parent, title):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        ttk.Label(frame, text=title, style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 10))
        return frame

    def _build_ui(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="MULTIMINER X 1.1", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Multi-asset payout routing · CPU RandomX + NVIDIA GPU PearlHash · research SHA-256d/SHA-512",
                  style="Sub.TLabel").pack(anchor="w", pady=(3, 0))

        top = ttk.Frame(root)
        top.pack(fill="x")
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=2)

        cfg = self._panel(top, "1. Cont și configurare de mining")
        cfg.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        info = self._panel(top, "2. Monitorizare locală")
        info.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.identity_var = tk.StringVar(value=self.settings["account_identity"])
        self.worker_var = tk.StringVar(value=self.settings["worker_name"])
        self.payout_var = tk.StringVar(value=self.settings["payout_label"])
        self.cpu_var = tk.IntVar(value=int(self.settings["cpu_percent"]))
        self.gpu_var = tk.IntVar(value=int(self.settings["gpu_intensity"]))
        self.temp_var = tk.IntVar(value=int(self.settings["gpu_stop_temp"]))
        self.autostop_var = tk.BooleanVar(value=bool(self.settings["auto_stop_temp"]))

        def add_entry(parent, label, var, row, width=38):
            ttk.Label(parent, text=label, style="Sub.TLabel").pack(anchor="w", pady=(3, 2))
            entry = ttk.Entry(parent, textvariable=var, width=width)
            entry.pack(fill="x", pady=(0, 5))
            return entry

        add_entry(cfg, "Alias cont unMineable (nu seed/private key) sau COIN:ADRESĂ pentru legacy", self.identity_var, 0)
        add_entry(cfg, "Nume worker", self.worker_var, 1)
        ttk.Label(cfg, text="Monedă payout (alege doar dacă apare disponibilă în contul unMineable)", style="Sub.TLabel").pack(anchor="w", pady=(3, 2))
        self.payout_combo = ttk.Combobox(cfg, textvariable=self.payout_var, values=PAYOUT_ASSET_CANDIDATES, state="normal", width=18)
        self.payout_combo.pack(anchor="w", fill="x", pady=(0, 5))
        ttk.Label(cfg, text="Profil CPU: RandomX (live) · SHA-256d/SHA-512 sunt doar laborator offline, nu pool-uri live.", style="Sub.TLabel", wraplength=590).pack(anchor="w", pady=(0, 5))
        row = ttk.Frame(cfg, style="Panel.TFrame")
        row.pack(fill="x", pady=(6, 4))
        ttk.Label(row, text="CPU threads hint (%)", style="Sub.TLabel").pack(side="left")
        ttk.Spinbox(row, from_=25, to=100, increment=5, textvariable=self.cpu_var, width=7).pack(side="left", padx=8)
        ttk.Label(row, text="GPU intensity (0–31)", style="Sub.TLabel").pack(side="left", padx=(18, 0))
        ttk.Spinbox(row, from_=8, to=31, increment=1, textvariable=self.gpu_var, width=7).pack(side="left", padx=8)
        row2 = ttk.Frame(cfg, style="Panel.TFrame")
        row2.pack(fill="x", pady=4)
        ttk.Checkbutton(row2, text="Oprește GPU la temperatura-limită", variable=self.autostop_var).pack(side="left")
        ttk.Label(row2, text="Limită °C", style="Sub.TLabel").pack(side="left", padx=(12, 4))
        ttk.Spinbox(row2, from_=70, to=88, increment=1, textvariable=self.temp_var, width=5).pack(side="left")
        ttk.Label(cfg, text="Preset sigur: CPU 50% hint + GPU intensity 16/31. Nu înseamnă 50% utilizare exactă pentru ambele componente.",
                  style="Sub.TLabel", wraplength=590).pack(anchor="w", pady=(5, 8))
        btnrow = ttk.Frame(cfg, style="Panel.TFrame")
        btnrow.pack(fill="x", pady=(3, 0))
        ttk.Button(btnrow, text="START CPU", command=self.start_cpu, style="Accent.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(btnrow, text="START GPU", command=self.start_gpu, style="Accent.TButton").pack(side="left", padx=6)
        ttk.Button(btnrow, text="START DUAL", command=self.start_dual, style="Accent.TButton").pack(side="left", padx=6)
        ttk.Button(btnrow, text="STOP ALL", command=self.stop_all, style="Stop.TButton").pack(side="right")
        ttk.Button(cfg, text="Salvează setările", command=self.save_settings).pack(anchor="e", pady=(8, 0))

        self.cpu_status = tk.StringVar(value="CPU: pregătit / oprit")
        self.gpu_status = tk.StringVar(value="GPU: pregătit / oprit")
        self.gpu_telemetry = tk.StringVar(value="NVIDIA telemetry: în așteptare")
        ttk.Label(info, textvariable=self.cpu_status, style="PanelTitle.TLabel").pack(anchor="w", pady=5)
        ttk.Label(info, textvariable=self.gpu_status, style="PanelTitle.TLabel").pack(anchor="w", pady=5)
        ttk.Separator(info).pack(fill="x", pady=9)
        ttk.Label(info, textvariable=self.gpu_telemetry, style="Sub.TLabel", wraplength=330).pack(anchor="w")
        logical = os.cpu_count() or 1
        plan = cpu_thread_plan(logical, 50)
        ttk.Label(info, text=f"CPU detectat: {logical} thread-uri logice · plan orientativ la 50%: {plan['worker_threads']} worker threads",
                  style="Sub.TLabel", wraplength=330).pack(anchor="w", pady=(10, 0))
        ttk.Label(info, text="Loguri: logs/cpu.log și logs/gpu.log", style="Sub.TLabel").pack(anchor="w", pady=(15, 0))
        ttk.Label(info, text="Închide unMiner înainte de START DUAL ca să nu pornești două seturi de miner-e pe același hardware.", style="Sub.TLabel", wraplength=330).pack(anchor="w", pady=(6, 0))

        math_panel = self._panel(root, "3. Motor matematic — șanse PoW, Monte Carlo și energie")
        math_panel.pack(fill="x", pady=(12, 8))
        inputs = ttk.Frame(math_panel, style="Panel.TFrame")
        inputs.pack(fill="x")
        self.user_hash_var = tk.StringVar(value="")
        self.network_hash_var = tk.StringVar(value="")
        self.block_time_var = tk.StringVar(value="")
        self.period_hours_var = tk.StringVar(value="24")
        self.reward_var = tk.StringVar(value="")
        self.power_var = tk.StringVar(value="")
        self.kwh_price_var = tk.StringVar(value="")
        fields = [("Hashrate propriu (H/s, algoritmul ales)", self.user_hash_var),
                  ("Hashrate rețea (H/s)", self.network_hash_var),
                  ("Timp bloc (secunde)", self.block_time_var),
                  ("Perioadă (ore)", self.period_hours_var),
                  ("Recompensă / bloc (opțional)", self.reward_var),
                  ("Consum total laptop (W, măsurat/estimat)", self.power_var),
                  ("Preț energie (lei/kWh)", self.kwh_price_var)]
        for i, (label, var) in enumerate(fields):
            cell = ttk.Frame(inputs, style="Panel.TFrame")
            cell.grid(row=i // 4, column=i % 4, padx=5, pady=3, sticky="ew")
            ttk.Label(cell, text=label, style="Sub.TLabel", wraplength=205).pack(anchor="w")
            ttk.Entry(cell, textvariable=var, width=22).pack(fill="x")
        for col in range(4):
            inputs.columnconfigure(col, weight=1)
        ttk.Button(math_panel, text="Calculează probabilitatea + simulare Monte Carlo", command=self.calculate).pack(anchor="e", pady=(8, 4))
        self.math_result = tk.StringVar(value="Introduceți hashrate-ul actual al aceleiași rețele/algoritm. Nu comparați MH/s dintr-un algoritm cu TH/s din altul.")
        ttk.Label(math_panel, textvariable=self.math_result, style="Sub.TLabel", wraplength=960, justify="left").pack(anchor="w")

        logpanel = self._panel(root, "4. Jurnal live")
        logpanel.pack(fill="both", expand=True, pady=(0, 2))
        self.log_text = tk.Text(logpanel, height=12, bg="#081018", fg="#c8e6d5", insertbackground="#ffffff",
                                relief="flat", wrap="word", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", "MULTIMINER X 1.1 gata. Verifică tickerul payout în dashboard înainte de mining. Instalează motoarele oficiale cu INSTALL_BACKENDS.ps1.\n")
        self.log_text.configure(state="disabled")
        ttk.Label(root, text="Siguranță: nu introduce seed phrase/private key. Nu dezactiva antivirusul. Nu activăm overclock/eficiency tuner automat.",
                  style="Sub.TLabel").pack(anchor="w", pady=(7, 0))

    def log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        # Keep the live view bounded; full output remains in logs/*.log.
        try:
            if int(self.log_text.index("end-1c").split(".")[0]) > 1500:
                self.log_text.delete("1.0", "500.0")
        except Exception:
            pass
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def save_settings(self):
        try:
            self._validated()
            values = {
                "account_identity": self.identity_var.get().strip(),
                "worker_name": self.worker_var.get().strip(),
                "payout_label": self.payout_var.get().strip().upper(),
                "cpu_percent": int(self.cpu_var.get()),
                "gpu_intensity": int(self.gpu_var.get()),
                "gpu_stop_temp": int(self.temp_var.get()),
                "auto_stop_temp": bool(self.autostop_var.get()),
            }
            if not 25 <= values["cpu_percent"] <= 100:
                raise ValueError("CPU hint trebuie să fie între 25 și 100%.")
            if not 8 <= values["gpu_intensity"] <= 31:
                raise ValueError("GPU intensity trebuie să fie între 8 și 31.")
            if not 70 <= values["gpu_stop_temp"] <= 88:
                raise ValueError("Temperatura-limită trebuie să fie între 70 și 88°C.")
            write_settings(values)
            self.settings = values
            self.log("Setări salvate local în config/settings.json.")
            return True
        except Exception as exc:
            messagebox.showerror("Setări invalide", str(exc))
            return False

    def _validated(self):
        self.save_settings()
        identity = validate_identity(self.identity_var.get(), self.worker_var.get())
        return identity

    def start_cpu(self):
        if not self.save_settings():
            return
        try:
            identity = validate_identity(self.identity_var.get(), self.worker_var.get())
            identity = format_payout_identity(identity, self.payout_var.get())
            exe = locate_exe(app_resource("xmrig"), "xmrig.exe")
            # Dedicated config prevents an old autosaved XMRig profile from overriding the 50% hint.
            cpu_config = {
                "autosave": False,
                "background": False,
                "colors": False,
                "cpu": {"enabled": True, "yield": True, "max-threads-hint": int(self.cpu_var.get())},
                "opencl": {"enabled": False},
                "cuda": {"enabled": False},
                "pools": [{
                    "algo": "rx/0", "coin": "monero",
                    "url": "stratum+ssl://rx.unmineable.com:443",
                    "user": identity, "pass": "x", "keepalive": True,
                    "enabled": True, "tls": True
                }]
            }
            cpu_config_path = ROOT / "config" / "xmrig_cpu.json"
            cpu_config_path.write_text(json.dumps(cpu_config, indent=2), encoding="utf-8")
            args = [f"--config={cpu_config_path}", "--no-color", "--donate-level", "1"]
            self.controller.start("CPU", exe, args)
            self.log(f"CPU RandomX: XMRig -> rx.unmineable.com:443 (TLS), payout={self.payout_var.get().upper()}, hint {self.cpu_var.get()}%.")
        except Exception as exc:
            messagebox.showerror("Nu pot porni CPU", str(exc))

    def start_gpu(self):
        if not self.save_settings():
            return
        try:
            identity = validate_identity(self.identity_var.get(), self.worker_var.get())
            identity = format_payout_identity(identity, self.payout_var.get())
            exe = locate_exe(app_resource("srbminer"), "SRBMiner-MULTI.exe")
            args = ["--algorithm", "pearlhash", "--disable-cpu",
                    "--pool", "stratum+ssl://pearlpow.unmineable.com:4444",
                    "--wallet", identity, "--password", "x",
                    "--gpu-intensity", str(int(self.gpu_var.get()))]
            if self.autostop_var.get():
                args += ["--gpu-off-temperature", str(int(self.temp_var.get()))]
            self.controller.start("GPU", exe, args)
            self.log(f"GPU PearlPow: SRBMiner -> pearlpow.unmineable.com:4444 (TLS), payout={self.payout_var.get().upper()}, intensity {self.gpu_var.get()}/31.")
        except Exception as exc:
            messagebox.showerror("Nu pot porni GPU", str(exc))

    def start_dual(self):
        self.start_cpu()
        self.after(1200, self.start_gpu)

    def stop_all(self):
        threading.Thread(target=self.controller.stop_all, daemon=True).start()
        self.log("Comandă STOP ALL trimisă.")

    def calculate(self):
        try:
            user = float(self.user_hash_var.get())
            net = float(self.network_hash_var.get())
            block_s = float(self.block_time_var.get())
            hours = float(self.period_hours_var.get())
            power = float(self.power_var.get())
            tariff = float(self.kwh_price_var.get())
            if any(x <= 0 for x in (user, net, block_s, hours)):
                raise ValueError("Hashrate, timp bloc și perioadă trebuie să fie pozitive.")
            p = probability_at_least_one_block(user, net, block_s, hours * 3600)
            exp = expected_blocks(user, net, block_s, hours * 3600)
            wait = expected_wait_seconds(user, net, block_s)
            mc = monte_carlo_block_probability(user, net, block_s, hours * 3600, trials=100_000)
            kwh = energy_kwh(power, hours)
            cost = electricity_cost(power, hours, tariff)
            wait_text = "infinit" if wait == float("inf") else f"{wait / 86400:,.2f} zile"
            reward_line = ""
            if self.reward_var.get().strip():
                reward = float(self.reward_var.get())
                if reward < 0:
                    raise ValueError("Recompensa nu poate fi negativă.")
                reward_line = f"\nRecompensă brută așteptată: {exp * reward:,.8g} coin în {hours:g} h (valoare statistică, nu plată garantată)."
            self.math_result.set(
                f"P(≥1 bloc) analitic: {p*100:.8g}% | Monte Carlo 100k: {mc['estimate']*100:.8g}% "
                f"(SE {mc['standard_error']*100:.4g} pp)\nBlocuri așteptate: {exp:.8g} | Timp mediu statistic până la bloc: {wait_text}."
                f"{reward_line}\nEnergie: {kwh:.3f} kWh | Cost estimat: {cost:.2f} lei. "
                "Atenție: Monte Carlo doar verifică probabilitatea Poisson; nu prezice hash-uri și nu îmbunătățește șansa reală."
            )
            self.log("Calcul matematic terminat (analitic + Monte Carlo).")
        except Exception as exc:
            messagebox.showerror("Date de calcul invalide", str(exc))

    def _drain_events(self):
        try:
            while True:
                kind, name, payload = self.events.get_nowait()
                if kind == "log":
                    # Keep console manageable but do not alter the miner's own complete log files.
                    if payload:
                        self.log(f"[{name}] {payload}")
                elif kind == "state":
                    (self.cpu_status if name == "CPU" else self.gpu_status).set(f"{name}: {payload}")
                    self.log(f"[{name}] {payload}")
                elif kind == "exit":
                    status = "oprit" if payload == 0 else f"proces încheiat (cod {payload})"
                    (self.cpu_status if name == "CPU" else self.gpu_status).set(f"{name}: {status}")
                elif kind == "telemetry":
                    self.gpu_telemetry.set(payload)
        except queue.Empty:
            pass
        self.after(250, self._drain_events)

    def _poll_gpu_telemetry(self):
        if not self._monitor_running:
            self._monitor_running = True
            limit = int(self.temp_var.get())
            autostop = bool(self.autostop_var.get())
            threading.Thread(target=self._telemetry_worker, args=(limit, autostop), daemon=True).start()
        self.after(8000, self._poll_gpu_telemetry)

    def _telemetry_worker(self, limit: int, autostop: bool):
        try:
            cp = subprocess.run(["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total",
                                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
            if cp.returncode == 0 and cp.stdout.strip():
                raw = cp.stdout.strip().splitlines()[0]
                parts = [x.strip() for x in raw.split(",")]
                if len(parts) >= 6:
                    name, temp, util, power, used, total = parts[:6]
                    self.events.put(("telemetry", "GPU", f"{name} | {temp}°C | load {util}% | {power} W | VRAM {used}/{total} MiB"))
                    try:
                        if autostop and float(temp) >= limit and self.controller.status("GPU"):
                            self.events.put(("log", "GPU", f"Protecție termică: {temp}°C ≥ {limit}°C. Oprire GPU."))
                            self.controller.stop("GPU")
                    except Exception:
                        pass
            else:
                self.events.put(("telemetry", "GPU", "nvidia-smi indisponibil; verifică driverul NVIDIA."))
        except FileNotFoundError:
            self.events.put(("telemetry", "GPU", "nvidia-smi nu a fost găsit; telemetry indisponibilă."))
        except Exception as exc:
            self.events.put(("telemetry", "GPU", f"Telemetry indisponibilă: {exc}"))
        finally:
            self._monitor_running = False

    def _on_close(self):
        if self.controller.status("CPU") or self.controller.status("GPU"):
            if not messagebox.askyesno("Miner activ", "Există procese de mining active. Oprești miner-ele și închizi aplicația?"):
                return
            self.controller.stop_all()
        self.destroy()


if __name__ == "__main__":
    MinerApp().mainloop()
