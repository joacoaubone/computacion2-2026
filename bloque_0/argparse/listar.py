import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description="Lista archivos de un directorio")

parser.add_argument("directorio", nargs="?", default=".", help="Directorio a listar")
parser.add_argument("-a", "--all", action="store_true", help="Mostrar archivos ocultos")
parser.add_argument("--extension", help="Filtrar por extensión (ej: .py)")

args = parser.parse_args()

ruta = Path(args.directorio)


if not ruta.exists() or not ruta.is_dir():
    print(f"Error: '{args.directorio}' no es un directorio válido")
    exit(1)


for item in ruta.iterdir():

    nombre = item.name

    # ocultos
    if not args.all and nombre.startswith("."):
        continue

    # filtro por extensión
    if args.extension and item.is_file():
        if not nombre.endswith(args.extension):
            continue

    # mostrar con /
    if item.is_dir():
        print(nombre + "/")
    else:
        print(nombre)