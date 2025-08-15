
# Simulador de gestión de procesos con memoria fija y procesos predefinidos
# Se agrega la administracion de memoria En tiempo y tamaño Manejo de Procesos

import threading
import time

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
            self.used_mb -= mem_mb

    def stats(self):
        return f"RAM usada: {self.used_mb}/{self.total_mb} MB"

class Scheduler:
    def __init__(self, mm):
        self.mm = mm
        self.queue = []
        self.running = []

    def add_process(self, process):
        self.queue.append(process)

    def run(self):
        while self.queue:
            p = self.queue.pop(0)
            if self.mm.try_alloc(p.mem_mb):
                p.state = "RUNNING"
                print(f"Iniciando {p.name} ({p.mem_mb}MB) - {self.mm.stats()}")
                t = threading.Thread(target=self._run_process, args=(p,), daemon=True)
                t.start()
                self.running.append(p)
            else:
                print(f"Sin memoria para {p.name}, quedará en espera.")

            time.sleep(0.5)

    def _run_process(self, p):
        time.sleep(p.duration_s)
        p.state = "FINISHED"
        self.mm.free(p.mem_mb)
        print(f"Finalizó {p.name}, liberó {p.mem_mb}MB - {self.mm.stats()}")

# Ejecución de ejemplo
mm = MemoryManager(1024)
sch = Scheduler(mm)
sch.add_process(Process(1, "Editor", 200, 5))
sch.add_process(Process(2, "Compilador", 600, 4))
sch.add_process(Process(3, "Navegador", 400, 3))
sch.add_process(Process(4, "Terminal", 100, 2))
sch.run()
