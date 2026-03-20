import time
from contextlib import contextmanager

# VERSION 1
class TimerClase:
    def __init__(self, nombre=None):
        self.nombre = nombre
        self.inicio = None

    def __enter__(self):
        self.inicio = time.time()
        return self 

    def __exit__(self, tipo_exc, valor_exc, traceback):
        if self.nombre:
            print(f"[Timer] {self.nombre}: {self.elapsed:.3f}s")

        return False 
    
    @property
    def elapsed(self):
        return time.time() - self.inicio if self.inicio else 0

# VERSION 2
@contextmanager
def Timer(nombre=None):
    inicio = time.time()

    class T:
        @property
        def elapsed(self):
            return time.time() - inicio

    t = T()

    try:
        yield t
    finally:
        if nombre:
            print(f"[Timer] {nombre}: {t.elapsed:.3f}s")
    
def paso1():
    time.sleep(0.3)

def paso2():
    time.sleep(0.2)

# PRUEBA VERSION 1
with TimerClase("Procesamiento de datos"):
    datos = [x**2 for x in range(1000000)]
# [Timer] Procesamiento de datos: 0.123s

# También debe funcionar sin nombre
with TimerClase() as t:
    time.sleep(0.5)
print(f"El bloque tardó {t.elapsed:.3f} segundos")
# El bloque tardó 0.502 segundos

# Y permitir acceso al tiempo antes de salir
with TimerClase() as t:
    paso1()
    print(f"Después del paso 1: {t.elapsed:.3f}s")
    paso2()
    print(f"Después del paso 2: {t.elapsed:.3f}s")


# PRUEBA VERSION 2
with Timer("Procesamiento de datos"):
    datos = [x**2 for x in range(1000000)]
# [Timer] Procesamiento de datos: 0.123s

# También debe funcionar sin nombre
with Timer() as t:
    time.sleep(0.5)
print(f"El bloque tardó {t.elapsed:.3f} segundos")
# El bloque tardó 0.502 segundos

# Y permitir acceso al tiempo antes de salir
with Timer() as t:
    paso1()
    print(f"Después del paso 1: {t.elapsed:.3f}s")
    paso2()
    print(f"Después del paso 2: {t.elapsed:.3f}s")