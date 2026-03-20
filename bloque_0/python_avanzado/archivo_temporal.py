from contextlib import contextmanager
import os

@contextmanager
def archivo_temporal(nombre):
    f = open(nombre, "w+")
    try:
        yield f
    finally:
        f.close()
        if os.path.exists(nombre):
            os.remove(nombre)


with archivo_temporal("test.txt") as f:
    f.write("Datos de prueba\n")
    f.write("Más datos\n")
    f.seek(0)
    print(f.read())

import os
print(os.path.exists("test.txt"))