from functools import wraps
from inspect import signature

def validate_types(func):
    sig = signature(func)
    annotations = func.__annotations__

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        for nombre, valor in bound.arguments.items():
            if nombre in annotations:
                tipo_esperado = annotations[nombre]
                if not isinstance(valor, tipo_esperado):
                    raise TypeError(
                        f"'{nombre}' debe ser {tipo_esperado.__name__}, "
                        f"recibido {type(valor).__name__}"
                    )

        resultado = func(*args, **kwargs)

        if "return" in annotations:
            tipo_retorno = annotations["return"]
            if not isinstance(resultado, tipo_retorno):
                raise TypeError(
                    f"retorno debe ser {tipo_retorno.__name__}, "
                    f"recibido {type(resultado).__name__}"
                )

        return resultado

    return wrapper


@validate_types
def procesar(nombre: str, edad: int, activo: bool = True) -> str:
    return f"{nombre} tiene {edad} años"


@validate_types
def sumar(a: int, b: int) -> int:
    return str(a + b)  # error a propósito


# Casos OK
print(procesar("Ana", 25))
print(procesar("Ana", 25, False))

# Casos con error
try:
    print(procesar("Ana", "25"))
except TypeError as e:
    print("Error:", e)

try:
    print(procesar(123, 25))
except TypeError as e:
    print("Error:", e)

try:
    print(sumar(1, 2))
except TypeError as e:
    print("Error:", e)