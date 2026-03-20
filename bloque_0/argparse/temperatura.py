import argparse

parser = argparse.ArgumentParser(
    description="Convierte temperaturas entre Celsius y Fahrenheit."
)

parser.add_argument("valor", type=float, help="Temperatura a convertir")
parser.add_argument(
    "-t", "--to",
    required=True,
    choices=["celsius", "fahrenheit"],
    help="Unidad de destino"
)

args = parser.parse_args()

valor = args.valor
destino = args.to

if destino == "fahrenheit":
    resultado = valor * 9/5 + 32
    print(f"{valor}°C = {resultado}°F")
else:
    resultado = (valor - 32) * 5/9
    print(f"{valor}°F = {resultado:.2f}°C")