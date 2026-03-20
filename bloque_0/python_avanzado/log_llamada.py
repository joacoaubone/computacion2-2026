from functools import wraps
from datetime import datetime

def log_llamada(funcion):
    @wraps(funcion)
    def wrapper(*args, **kwargs):

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        args_str = ", ".join(repr(a) for a in args)
        kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())

        if args and kwargs:
            argumentos = f"{args_str}, {kwargs_str}"
        else:
            argumentos = args_str or kwargs_str

        print(f"[{timestamp}] Llamando a {funcion.__name__}({argumentos})")

        resultado = funcion(*args, **kwargs)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{timestamp}] {funcion.__name__} retornó {repr(resultado)}")

        return resultado

    return wrapper

@log_llamada
def sumar(a, b):
    return a + b

@log_llamada
def saludar(nombre, entusiasta=False):
    sufijo = "!" if entusiasta else "."
    return f"Hola, {nombre}{sufijo}"

resultado = sumar(3, 5)

saludar("Ana", entusiasta=True)