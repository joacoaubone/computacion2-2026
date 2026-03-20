from functools import wraps

def pipeline_decorador(*funciones):
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            resultado = func(*args, **kwargs)
            for f in funciones:
                resultado = f(resultado)
            return resultado
        return wrapper
    return decorador

def pipeline(*funciones):
    def ejecutar(resultado):
        for f in funciones:
            resultado = f(resultado)
        return resultado
    return ejecutar

def doble(x): return x * 2
def sumar_uno(x): return x + 1
def cuadrado(x): return x ** 2

# Pipeline normal
p = pipeline(doble, sumar_uno, cuadrado)

print(p(3))  # 49
print(p(5))  # 121

# Una sola función
p2 = pipeline(doble)
print(p2(10))  # 20

# Varias funciones
p3 = pipeline(str, len, doble)
print(p3(12345))  # 10

@pipeline_decorador(str.strip, str.lower, str.split)
def procesar_entrada(texto):
    return texto

print(procesar_entrada("  HELLO WORLD  "))
# ['hello', 'world']