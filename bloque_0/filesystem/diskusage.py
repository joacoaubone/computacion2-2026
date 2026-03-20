from pathlib import Path
import argparse
import sys
import fnmatch


def parse_excludes(exclude_str):
    if not exclude_str:
        return []
    return [pat.strip() for pat in exclude_str.split(",")]


def esta_excluido(path, patrones):
    for patron in patrones:
        if fnmatch.fnmatch(path.name, patron):
            return True
    return False


def calcular_tamano(path, patrones):
    """
    Calcula tamaño total de un archivo o directorio.
    """
    try:
        if esta_excluido(path, patrones):
            return 0

        if path.is_file():
            return path.stat().st_size

        elif path.is_dir():
            total = 0
            for item in path.iterdir():
                total += calcular_tamano(item, patrones)
            return total

    except (PermissionError, FileNotFoundError):
        return 0

    return 0


def tamano_legible(bytes):
    for unidad in ["B", "K", "M", "G", "T"]:
        if bytes < 1024:
            return f"{bytes:.1f}{unidad}"
        bytes /= 1024
    return f"{bytes:.1f}P"


def analizar_directorio(base, depth, patrones):
    resultados = []

    for item in base.iterdir():
        if esta_excluido(item, patrones):
            continue

        size = calcular_tamano(item, patrones)
        resultados.append((item, size))

        if depth > 1 and item.is_dir():
            resultados.extend(
                analizar_directorio(item, depth - 1, patrones)
            )

    return resultados


def main():
    parser = argparse.ArgumentParser(
        description="Analiza uso de disco"
    )

    parser.add_argument("directorio")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--top", type=int)
    parser.add_argument("--exclude", type=str)
    parser.add_argument("--human", action="store_true", default=True)

    args = parser.parse_args()

    base = Path(args.directorio)

    if not base.exists():
        print("Error: el directorio no existe")
        sys.exit(1)

    patrones = parse_excludes(args.exclude)

    resultados = analizar_directorio(base, args.depth, patrones)

    total = sum(size for _, size in resultados)

    resultados.sort(key=lambda x: x[1], reverse=True)

    if args.top:
        print(f"Los {args.top} archivos/carpetas más grandes:")
        resultados = resultados[:args.top]

    for path, size in resultados:
        if args.human:
            size_str = tamano_legible(size)
        else:
            size_str = str(size)

        print(f"{size_str}\t{path}")

    print("─" * 30)

    if args.human:
        print(f"Total: {tamano_legible(total)}")
    else:
        print(f"Total: {total} bytes")


if __name__ == "__main__":
    main()