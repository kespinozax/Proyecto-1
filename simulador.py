#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Versión 3: Simulador de Gestión de Procesos en Memoria
- Soporte para agregar procesos por comando (--add)
- Modo demo (--demo) con procesos predefinidos
- Carga de procesos desde archivo JSON (--load)
- Memoria total configurable (--ram)
- Timestamps en salida
- Cola de procesos automática sin advertencias
"""

import threading
import time
import argparse
import json
import os
from collections import deque
from typing import Optional

# -------------------- Utilidades --------------------
def ts() -> str:
    """Devuelve timestamp en formato HH:MM:SS"""
    return time.strftime("%H:%M:%S")

# -------------------- Modelo --------------------
class Process:
    def __init__(self, pid: int, name: str, mem_mb: int, duration_s: float):
        self.pid = pid
        self.name = name
        self.mem_mb = mem_mb
        self.duration_s = duration_s
        self.state = "WAITING"

class MemoryManager:
    def __init__(self, total_mb=1024):
        self.total_mb = total_mb
        self.used_mb = 0
        self.lock = threading.Lock()

    def try_alloc(self, mem_mb):
        with self.lock:
            if self.used_mb + mem_mb <= self.total_mb:
                self.used_mb += mem_mb
                return True
            return False

    def free(self, mem_mb):
        with self.lock:
            self.used_mb = max(0, self.used_mb - mem_mb)

    def stats(self):
        with self.lock:
            return f"RAM usada: {self.used_mb}/{self.total_mb} MB"

class Scheduler:
    def __init__(self, mm: MemoryManager):
        self.mm = mm
        self.queue = deque()
        self.running = {}
        self.next_pid = 1
        self.lock = threading.Lock()

    def add_process(self, name: str, mem_mb: int, duration_s: float, pid: Optional[int]=None):
        with self.lock:
            if pid is None:
                pid = self.next_pid
                self.next_pid += 1
            else:
                if pid >= self.next_pid:
                    self.next_pid = pid + 1
            p = Process(pid, name, mem_mb, duration_s)
            self.queue.append(p)
        print(f"[{ts()}] + ADD PID={p.pid:03d} '{p.name}' mem={p.mem_mb}MB dur={p.duration_s}s -> cola")

    def _start_if_possible(self):
        started_any = False
        while True:
            with self.lock:
                if not self.queue:
                    break
                p = self.queue[0]
            if self.mm.try_alloc(p.mem_mb):
                with self.lock:
                    self.queue.popleft()
                    self.running[p.pid] = p
                    p.state = "RUNNING"
                print(f"[{ts()}] > START PID={p.pid:03d} '{p.name}' ({p.mem_mb}MB) - {self.mm.stats()}")
                t = threading.Thread(target=self._run_process, args=(p,), daemon=True)
                t.start()
                started_any = True
            else:
                break
        return started_any

    def _run_process(self, p: Process):
        time.sleep(p.duration_s)
        p.state = "FINISHED"
        self.mm.free(p.mem_mb)
        with self.lock:
            self.running.pop(p.pid, None)
        print(f"[{ts()}] < END   PID={p.pid:03d} '{p.name}' liberó {p.mem_mb}MB - {self.mm.stats()}")

    def run(self):
        print(f"[{ts()}] === INICIO DEL SCHEDULER ===")
        while True:
            self._start_if_possible()
            with self.lock:
                nothing_left = (not self.running) and (not self.queue)
            if nothing_left:
                break
            time.sleep(0.1)
        print(f"[{ts()}] === FIN DEL SCHEDULER ===")
        print(f"[{ts()}] {self.mm.stats()}")

# -------------------- CLI --------------------
def parse_add_arg(arg: str):
    """Parsea: mem=100,dur=5,name=Algo[,pid=10]"""
    kv = dict(item.split("=") for item in arg.split(","))
    name = kv.get("name", "proc")
    mem = int(kv.get("mem", "0"))
    dur = float(kv.get("dur", "0"))
    pid = int(kv["pid"]) if "pid" in kv else None
    return name, mem, dur, pid

def main():
    parser = argparse.ArgumentParser(description="Simulador de Gestión de Procesos en Memoria (V3)")
    parser.add_argument("--add", action="append", help='Agregar proceso: "mem=100,dur=5,name=Editor"')
    parser.add_argument("--demo", action="store_true", help="Ejecuta demostración con procesos predefinidos")
    parser.add_argument("--load", type=str, help="Cargar procesos desde archivo JSON")
    parser.add_argument("--ram", type=int, default=1024, help="RAM total en MB")
    args = parser.parse_args()

    mm = MemoryManager(total_mb=args.ram)
    sch = Scheduler(mm)

    # -------- Demo --------
    if args.demo:
        demo_processes = [
            ("Editor", 200, 5),
            ("Compilador", 600, 6),
            ("Navegador", 400, 4),
            ("Terminal", 100, 3),
            ("Autoname", 256, 2)
        ]
        for name, mem, dur in demo_processes:
            sch.add_process(name, mem, dur)

    # -------- JSON --------
    if args.load:
        if not os.path.exists(args.load):
            raise SystemExit(f"Archivo no encontrado: {args.load}")
        with open(args.load, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise SystemExit("El JSON debe ser una lista de procesos")
        for item in data:
            sch.add_process(
                name=item.get("name", f"proc"),
                mem_mb=int(item.get("mem", item.get("mem_mb", 0))),
                duration_s=float(item.get("dur", item.get("duration", 0))),
                pid=item.get("pid")
            )

    # -------- Procesos por comando --------
    if args.add:
        for spec in args.add:
            name, mem, dur, pid = parse_add_arg(spec)
            sch.add_process(name, mem, dur, pid)

    # -------- Validación mínima --------
    if not args.add and not args.demo and not args.load:
        print("No se especificaron procesos. Use --demo, --add o --load")
        parser.print_help()
        return

    # -------- Ejecutar Scheduler --------
    sch.run()

if __name__ == "__main__":
    main()
