#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Versión 2 Mejorada: Simulador de Gestión de Procesos en Memoria
- Soporte para agregar procesos por comando (--add)
- Modo demo (--demo) con procesos predefinidos (igual que V1)
- Memoria total configurable (--ram)
- Timestamps en salida
- Cola de procesos que espera automáticamente sin mostrar advertencias
"""

import threading
import time
import argparse
from collections import deque

# -------------------- Utilidades --------------------
def ts() -> str:
    """Devuelve timestamp en formato HH:MM:SS"""
    return time.strftime("%H:%M:%S")

# -------------------- Modelo --------------------
class Process:
    def __init__(self, pid, name, mem_mb, duration_s):
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
    def __init__(self, mm):
        self.mm = mm
        self.queue = deque()
        self.running = {}
        self.next_pid = 1
        self.lock = threading.Lock()

    def add_process(self, name, mem_mb, duration_s):
        with self.lock:
            p = Process(self.next_pid, name, mem_mb, duration_s)
            self.next_pid += 1
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
                # No hay memoria para el primer proceso, salir y esperar
                break
        return started_any

    def _run_process(self, p):
        time.sleep(p.duration_s)
        p.state = "FINISHED"
        self.mm.free(p.mem_mb)
        with self.lock:
            self.running.pop(p.pid, None)
        print(f"[{ts()}] < END   PID={p.pid:03d} '{p.name}' liberó {p.mem_mb}MB - {self.mm.stats()}")

    def run(self):
        print(f"[{ts()}] === INICIO DEL SCHEDULER ===")
        while True:
            progressed = self._start_if_possible()
            with self.lock:
                nothing_left = (not self.running) and (not self.queue)
            if nothing_left:
                break
            # Espera breve antes de reintentar procesos en cola
            time.sleep(0.1)
        print(f"[{ts()}] === FIN DEL SCHEDULER ===")
        print(f"[{ts()}] {self.mm.stats()}")

# -------------------- CLI --------------------
def parse_add_arg(arg: str):
    """Parsea: mem=100,dur=5,name=Algo"""
    kv = dict(item.split("=") for item in arg.split(","))
    name = kv.get("name", f"proc")
    mem = int(kv.get("mem", "0"))
    dur = float(kv.get("dur", "0"))
    return name, mem, dur

def main():
    parser = argparse.ArgumentParser(description="Simulador de Gestión de Procesos en Memoria (V2)")
    parser.add_argument("--add", action="append", help='Agregar proceso: "mem=100,dur=5,name=Editor"')
    parser.add_argument("--demo", action="store_true", help="Ejecuta demostración con procesos predefinidos")
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

    # -------- Procesos por comando --------
    if args.add:
        for spec in args.add:
            name, mem, dur = parse_add_arg(spec)
            sch.add_process(name, mem, dur)

    # -------- Validación mínima --------
    if not args.add and not args.demo:
        print("No se especificaron procesos. Use --demo o --add")
        parser.print_help()
        return

    # -------- Ejecutar Scheduler --------
    sch.run()

if __name__ == "__main__":
    main()
