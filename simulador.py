#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simulador de Gestión de Procesos en Memoria (RAM) - V4
- RAM total: configurable (default 1 GB = 1024 MB)
- Gestión dinámica de memoria
- Cola de espera para procesos sin memoria suficiente
- Ejecución concurrente de procesos mientras haya memoria disponible
- Liberación automática de memoria al finalizar los procesos
- Estado en tiempo real: memoria y procesos en ejecución/cola
- Procesos que exceden RAM total se descartan con alerta
- Compatible con --demo, --add y --load JSON
"""

import argparse
import threading
import time
import uuid
import json
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict

# -------------------- Utilidades --------------------

def now_ms() -> int:
    return int(time.time() * 1000)

def ts() -> str:
    return time.strftime("%H:%M:%S")

# -------------------- Modelo --------------------

@dataclass
class Process:
    pid: int
    name: str
    mem_mb: int
    duration_s: float
    state: str = field(default="WAITING")  # WAITING | RUNNING | FINISHED
    t_start: Optional[float] = field(default=None)
    t_end: Optional[float] = field(default=None)

class MemoryManager:
    def __init__(self, total_mb: int = 1024):
        self.total_mb = total_mb
        self.used_mb = 0
        self.lock = threading.Lock()

    def try_alloc(self, pid: int, mem_mb: int) -> bool:
        with self.lock:
            if self.used_mb + mem_mb <= self.total_mb:
                self.used_mb += mem_mb
                return True
            return False

    def free(self, mem_mb: int) -> None:
        with self.lock:
            self.used_mb = max(0, self.used_mb - mem_mb)

    def stats(self) -> Dict[str, int]:
        with self.lock:
            return {
                "total_mb": self.total_mb,
                "used_mb": self.used_mb,
                "free_mb": self.total_mb - self.used_mb
            }

# -------------------- Scheduler --------------------

class Scheduler:
    def __init__(self, mm: MemoryManager):
        self.mm = mm
        self.queue: deque[Process] = deque()
        self.running: Dict[int, Process] = {}
        self.threads: Dict[int, threading.Thread] = {}
        self.lock = threading.Lock()
        self.next_pid = 1
        self._stop = False

    # ------- Creación / cola -------
    def _gen_pid(self) -> int:
        with self.lock:
            pid = self.next_pid
            self.next_pid += 1
        return pid

    def add_process(self, name: Optional[str], mem_mb: int, duration_s: float, pid: Optional[int]=None) -> Process:
        if pid is None:
            pid = self._gen_pid()
        if not name:
            name = f"proc-{uuid.uuid4().hex[:6]}"
        p = Process(pid=pid, name=name, mem_mb=mem_mb, duration_s=duration_s)
        with self.lock:
            self.queue.append(p)
        print(f"[{ts()}] + ADD   PID={p.pid:03d} '{p.name}' mem={p.mem_mb}MB dur={p.duration_s}s -> cola")
        return p

    # ------- Ejecución -------
    def _start_if_possible(self) -> None:
        started_any = False
        i = 0
        while i < len(self.queue):
            with self.lock:
                p = self.queue[i]

            # Proceso nunca ejecutable
            if p.mem_mb > self.mm.total_mb:
                print(f"[{ts()}] ! ERROR PID={p.pid:03d} '{p.name}' requiere {p.mem_mb}MB > RAM total {self.mm.total_mb}MB. Se descarta.")
                with self.lock:
                    self.queue.remove(p)
                continue

            # Proceso puede ejecutarse si hay memoria ahora
            if self.mm.try_alloc(p.pid, p.mem_mb):
                with self.lock:
                    self.queue.remove(p)
                    p.state = "RUNNING"
                    p.t_start = time.time()
                    self.running[p.pid] = p
                print(f"[{ts()}] > START PID={p.pid:03d} '{p.name}'  usa {p.mem_mb}MB | estado: {self._fmt_state()}")
                t = threading.Thread(target=self._run_process, args=(p,), daemon=True)
                self.threads[p.pid] = t
                t.start()
                started_any = True
                continue  # no incrementamos i porque removimos el proceso
            # No hay memoria suficiente ahora, siguiente en cola
            i += 1

        return started_any

    def _run_process(self, p: Process) -> None:
        time.sleep(p.duration_s)
        p.state = "FINISHED"
        p.t_end = time.time()
        self.mm.free(p.mem_mb)
        with self.lock:
            self.running.pop(p.pid, None)
        print(f"[{ts()}] < END   PID={p.pid:03d} '{p.name}' liberó {p.mem_mb}MB | estado: {self._fmt_state()}")

    def _fmt_state(self) -> str:
        st = self.mm.stats()
        with self.lock:
            running_pids = list(self.running.keys())
            qsize = len(self.queue)
        return f"RAM {st['used_mb']}/{st['total_mb']}MB (libre {st['free_mb']}MB) | running={running_pids} | cola={qsize}"

    def run(self) -> None:
        print(f"[{ts()}] === INICIO DEL SCHEDULER ===")
        print(f"[{ts()}] {self._fmt_state()}")
        while not self._stop:
            self._start_if_possible()
            with self.lock:
                nothing_left = (not self.running) and (not self.queue)
            if nothing_left:
                break
            time.sleep(0.1)
        print(f"[{ts()}] === FIN DEL SCHEDULER ===")
        print(f"[{ts()}] {self._fmt_state()}")

# -------------------- CLI --------------------

def parse_add_arg(arg: str) -> dict:
    kv = {}
    for part in arg.split(","):
        if not part.strip():
            continue
        k, _, v = part.partition("=")
        kv[k.strip()] = v.strip()
    out = {}
    if "pid" in kv:
        out["pid"] = int(kv["pid"])
    out["name"] = kv.get("name")
    out["mem"] = int(kv.get("mem", "0"))
    out["dur"] = float(kv.get("dur", "0"))
    return out

def main():
    parser = argparse.ArgumentParser(description="Simulador de Gestión de Procesos en Memoria (RAM)")
    parser.add_argument("--demo", action="store_true", help="Ejecuta demo de ejemplo")
    parser.add_argument("--load", type=str, help="Carga procesos desde archivo JSON")
    parser.add_argument("--add", action="append", help='Agregar proceso: "mem=100,dur=5,name=Navegador[,pid=42]"')
    parser.add_argument("--ram", type=int, default=1024, help="RAM total en MB")
    args = parser.parse_args()

    mm = MemoryManager(total_mb=args.ram)
    sch = Scheduler(mm)

    # --demo (igual que versión 1)
    if args.demo:
        sch.add_process("Editor", 200, 5)
        sch.add_process("Compilador", 600, 6)
        sch.add_process("Navegador", 400, 4)
        sch.add_process("Terminal", 100, 3)
        sch.add_process("Ejecutor", 256, 2)

    # --load JSON
    if args.load:
        if not os.path.exists(args.load):
            raise SystemExit(f"Archivo no encontrado: {args.load}")
        with open(args.load, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise SystemExit("JSON debe ser una lista de procesos")
        for item in data:
            sch.add_process(
                name=item.get("name"),
                mem_mb=int(item["mem"] if "mem" in item else item.get("mem_mb", 0)),
                duration_s=float(item["dur"] if "dur" in item else item.get("duration", 0)),
                pid=item.get("pid"),
            )

    # --add
    if args.add:
        for spec in args.add:
            d = parse_add_arg(spec)
            sch.add_process(d.get("name"), d["mem"], d["dur"], d.get("pid"))

    if not (args.demo or args.load or args.add):
        print("No se especificaron procesos. Use --demo, --load o --add.")
        parser.print_help()
        return

    # Ejecutar scheduler
    sch.run()

if __name__ == "__main__":
    main()
