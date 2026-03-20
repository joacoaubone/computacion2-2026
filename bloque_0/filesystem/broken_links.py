from pathlib import Path
import argparse
import os
import sys


def buscar_enlaces_rotos(directorio):
    enlaces_rotos = []

    for item in directorio.rglob("*"):
        try:
            if os.path.islink(item) and not os.path.exists(item):
                enlaces_rotos.append(item)
        except (PermissionError, FileNotFoundError):
            continue

    return enlaces_rotos


def mostrar_enlaces_rotos(enlaces_rotos):
    print("Enlaces rotos encontrados:")

    for enlace in enlaces_rotos:
        try:
            destino = os.readlink(enlace)
        except OSError:
            destino = "destino desconocido"

        print(f"  {enlace} -> {destino} (no existe)")

    print(f"\nTotal: {len(enlaces_rotos)} enlaces rotos")


def borrar_enlaces_rotos(enlaces_rotos):
    for enlace in enlaces_rotos:
        try:
            destino = os.readlink(enlace)
        except OSError:
            destino = "destino desconocido"

        respuesta = input(f"¿Borrar {enlace} -> {destino}? [si/no] ")

        if respuesta.lower() == "si":
            try:
                enlace.unlink()
                print("Borrado.")
            except OSError as e:
                print(f"Error al borrar {enlace}: {e}")
        else:
            print("Omitido.")


def main():
    parser = argparse.ArgumentParser(
        description="Busca enlaces simbólicos rotos de forma recursiva."
    )

    parser.add_argument("directorio", help="Directorio donde buscar")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Ofrecer borrar los enlaces rotos encontrados"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Mostrar solo la cantidad de enlaces rotos"
    )

    args = parser.parse_args()

    directorio = Path(args.directorio)

    if not directorio.exists():
        print(f"Error: '{directorio}' no existe")
        sys.exit(1)

    if not directorio.is_dir():
        print(f"Error: '{directorio}' no es un directorio")
        sys.exit(1)

    enlaces_rotos = buscar_enlaces_rotos(directorio)

    if args.quiet:
        print(len(enlaces_rotos))
        return

    print(f"Buscando enlaces simbólicos rotos en {directorio}...\n")

    if enlaces_rotos:
        mostrar_enlaces_rotos(enlaces_rotos)

        if args.delete:
            print()
            borrar_enlaces_rotos(enlaces_rotos)
    else:
        print("No se encontraron enlaces rotos.")
        print("Total: 0 enlaces rotos")


if __name__ == "__main__":
    main()