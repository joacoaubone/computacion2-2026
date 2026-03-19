import sys

suma = 0

for arg in sys.argv[1:]:
    try:
        numero = float(arg)
        suma += numero
    except ValueError:
        print(f"Advertencia: '{arg}' no es un número válido y se omitirá.")

print(f"La suma es: {suma}")