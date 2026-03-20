from pathlib import Path
import argparse
import sys


def parsear_tamano(valor):
    """
    Convierte strings como:
    100K -> 102400
    1M   -> 1048576
    2G   -> 2147483648
    500  -> 500
    """
    valor = valor.strip().upper()

    if valor[-1] in ["K", "M", "G"]:
        numero = float(valor[:-1])
        unidad = valor[-1]

        if unidad == "K":
            return int(numero * 1024)
        elif unidad == "M":
            return int(numero * 1024 * 1024)
        elif unidad == "G":
            return int(numero * 1024 * 1024 * 1024)
    else:
        return int(valor)


def tamano_legible(bytes_):
    """
    Convierte bytes a formato legible.
    """
    tamano = float(bytes_)

    for unidad in ["B", "KB", "MB", "GB", "TB"]:
        if tamano < 1024:
            return f"{tamano:.1f} {unidad}"
        tamano /= 1024

    return f"{tamano:.1f} PB"


def obtener_tamano_directorio(directorio):
    """
    Suma recursivamente el tamaño de todos los archivos
    dentro de un directorio.
    """
    total = 0

    try:
        for item in directorio.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except (PermissionError, FileNotFoundError):
                continue
    except (PermissionError, FileNotFoundError):
        return 0

    return total


def buscar_elementos(directorio, min_size, tipo):
    """
    Recorre recursivamente el directorio y devuelve una lista
    de tuplas: (ruta, tamano_en_bytes)
    """
    resultados = []

    for item in directorio.rglob("*"):
        try:
            if tipo == "f":
                if item.is_file():
                    size = item.stat().st_size
                    if size >= min_size:
                        resultados.append((item, size))

            elif tipo == "d":
                if item.is_dir():
                    size = obtener_tamano_directorio(item)
                    if size >= min_size:
                        resultados.append((item, size))

        except (PermissionError, FileNotFoundError):
            continue

    return resultados


def main():
    parser = argparse.ArgumentParser(
        description="Busca archivos o directorios grandes de forma recursiva."
    )

    parser.add_argument("directorio", help="Directorio donde buscar")
    parser.add_argument(
        "--min-size",
        default="0",
        help="Tamaño mínimo: por ejemplo 100K, 1M, 2G"
    )
    parser.add_argument(
        "--type",
        choices=["f", "d"],
        default="f",
        help="f = archivo, d = directorio"
    )
    parser.add_argument(
        "--top",
        type=int,
        help="Mostrar solo los N más grandes"
    )

    args = parser.parse_args()

    directorio = Path(args.directorio)

    if not directorio.exists():
        print(f"Error: '{directorio}' no existe")
        sys.exit(1)

    if not directorio.is_dir():
        print(f"Error: '{directorio}' no es un directorio")
        sys.exit(1)

    try:
        min_size = parsear_tamano(args.min_size)
    except ValueError:
        print("Error: tamaño inválido. Usá formatos como 100K, 1M o 2G")
        sys.exit(1)

    resultados = buscar_elementos(directorio, min_size, args.type)

    resultados.sort(key=lambda x: x[1], reverse=True)

    if args.top:
        resultados = resultados[:args.top]
        print(f"Los {len(resultados)} elementos más grandes:")

    total_archivos = len(resultados)
    total_bytes = sum(size for _, size in resultados)

    for i, (ruta, size) in enumerate(resultados, start=1):
        if args.top:
            print(f"{i}. {ruta} ({tamano_legible(size)})")
        else:
            print(f"{ruta} ({tamano_legible(size)})")

    print(f"Total: {total_archivos} elementos, {tamano_legible(total_bytes)}")


if __name__ == "__main__":
    main()