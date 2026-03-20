import argparse
import sys


def buscar_en_stream(stream, nombre, args, mostrar_nombre_archivo, mostrar_numero_linea):
    coincidencias = 0

    patron = args.patron
    if args.ignore_case:
        patron = patron.lower()

    for numero_linea, linea in enumerate(stream, start=1):
        linea_sin_salto = linea.rstrip("\n")

        texto_busqueda = linea_sin_salto
        if args.ignore_case:
            texto_busqueda = texto_busqueda.lower()

        coincide = patron in texto_busqueda

        if args.invert:
            coincide = not coincide

        if coincide:
            coincidencias += 1

            if not args.count:
                partes = []

                if mostrar_nombre_archivo:
                    partes.append(f"{nombre}:")

                if mostrar_numero_linea:
                    partes.append(f"{numero_linea}:")

                prefijo = "".join(partes)
                print(f"{prefijo}{linea_sin_salto}")

    return coincidencias


def main():
    parser = argparse.ArgumentParser(description="Mini-grep en Python")

    parser.add_argument("patron", help="Patrón a buscar")
    parser.add_argument("archivos", nargs="*", help="Archivos donde buscar")
    parser.add_argument("-i", "--ignore-case", action="store_true",
                        help="Ignorar mayúsculas/minúsculas")
    parser.add_argument("-n", "--line-number", action="store_true",
                        help="Mostrar número de línea")
    parser.add_argument("-c", "--count", action="store_true",
                        help="Mostrar solo el conteo de coincidencias")
    parser.add_argument("-v", "--invert", action="store_true",
                        help="Mostrar líneas que NO coinciden")

    args = parser.parse_args()

    total_coincidencias = 0

    # Caso 1: hay archivos
    if args.archivos:
        multiples_archivos = len(args.archivos) > 1
        mostrar_nombre_archivo = multiples_archivos
        mostrar_numero_linea = args.line_number or multiples_archivos

        for nombre_archivo in args.archivos:
            try:
                with open(nombre_archivo, "r", encoding="utf-8") as f:
                    coincidencias = buscar_en_stream(
                        f,
                        nombre_archivo,
                        args,
                        mostrar_nombre_archivo,
                        mostrar_numero_linea
                    )

                total_coincidencias += coincidencias

                if args.count:
                    print(f"{nombre_archivo}: {coincidencias} coincidencias")

            except FileNotFoundError:
                print(f"Error: no se puede leer '{nombre_archivo}'", file=sys.stderr)
            except PermissionError:
                print(f"Error: no se puede leer '{nombre_archivo}'", file=sys.stderr)
            except Exception:
                print(f"Error: no se puede leer '{nombre_archivo}'", file=sys.stderr)

        if args.count and len(args.archivos) > 1:
            print(f"Total: {total_coincidencias} coincidencias")

    # Caso 2: no hay archivos, leer de stdin
    else:
        if sys.stdin.isatty():
            print("Error: debe especificar al menos un archivo o enviar datos por stdin", file=sys.stderr)
            sys.exit(1)

        coincidencias = buscar_en_stream(
            sys.stdin,
            "",
            args,
            mostrar_nombre_archivo=False,
            mostrar_numero_linea=args.line_number
        )

        if args.count:
            print(f"{coincidencias} coincidencias")


if __name__ == "__main__":
    main()