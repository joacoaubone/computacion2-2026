import argparse
import json
import sys


def cargar_json(origen):
    """Carga JSON desde archivo o stdin."""
    try:
        if origen == "-":
            return json.load(sys.stdin)
        else:
            with open(origen, "r", encoding="utf-8") as f:
                return json.load(f)
    except FileNotFoundError:
        print(f"Error: no se puede leer '{origen}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: JSON inválido", file=sys.stderr)
        sys.exit(1)


def guardar_json(data, destino):
    """Guarda JSON en archivo o stdout."""
    try:
        if destino == "-":
            json.dump(data, sys.stdout, indent=4, ensure_ascii=False)
            print()
        else:
            with open(destino, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar JSON: {e}", file=sys.stderr)
        sys.exit(1)


def obtener_valor(data, path):
    """Obtiene un valor navegando un path con puntos."""
    actual = data
    partes = path.split(".")

    for parte in partes:
        if isinstance(actual, list):
            try:
                indice = int(parte)
                actual = actual[indice]
            except (ValueError, IndexError):
                print(f"Error: índice inválido '{parte}'", file=sys.stderr)
                sys.exit(1)

        elif isinstance(actual, dict):
            if parte not in actual:
                print(f"Error: clave inexistente '{parte}'", file=sys.stderr)
                sys.exit(1)
            actual = actual[parte]

        else:
            print(f"Error: no se puede acceder a '{parte}'", file=sys.stderr)
            sys.exit(1)

    return actual


def convertir_valor(valor):
    """Intenta convertir string a bool, int, float o null."""
    valor_lower = valor.lower()

    if valor_lower == "true":
        return True
    if valor_lower == "false":
        return False
    if valor_lower == "null":
        return None

    try:
        if "." in valor:
            return float(valor)
        return int(valor)
    except ValueError:
        return valor


def setear_valor(data, path, nuevo_valor):
    """Modifica o crea un valor navegando un path con puntos."""
    actual = data
    partes = path.split(".")

    for parte in partes[:-1]:
        if isinstance(actual, list):
            try:
                indice = int(parte)
                actual = actual[indice]
            except (ValueError, IndexError):
                print(f"Error: índice inválido '{parte}'", file=sys.stderr)
                sys.exit(1)

        elif isinstance(actual, dict):
            if parte not in actual:
                actual[parte] = {}
            actual = actual[parte]

        else:
            print(f"Error: no se puede acceder a '{parte}'", file=sys.stderr)
            sys.exit(1)

    ultima = partes[-1]

    if isinstance(actual, list):
        try:
            indice = int(ultima)
            actual[indice] = nuevo_valor
        except (ValueError, IndexError):
            print(f"Error: índice inválido '{ultima}'", file=sys.stderr)
            sys.exit(1)

    elif isinstance(actual, dict):
        actual[ultima] = nuevo_valor

    else:
        print(f"Error: no se puede asignar a '{ultima}'", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Procesador simple de JSON")

    parser.add_argument("archivo", help="Archivo JSON o - para stdin")
    parser.add_argument("--keys", action="store_true", help="Listar claves del primer nivel")
    parser.add_argument("--get", metavar="KEY", help="Obtener valor usando notación con puntos")
    parser.add_argument("--pretty", action="store_true", help="Mostrar JSON formateado")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"),
                        help="Modificar un valor usando notación con puntos")
    parser.add_argument("-o", "--output", default="-",
                        help="Archivo de salida (default: stdout)")

    args = parser.parse_args()

    acciones = [args.keys, args.get is not None, args.pretty, args.set is not None]
    if sum(acciones) != 1:
        print("Error: debe especificar exactamente una acción entre --keys, --get, --pretty o --set",
              file=sys.stderr)
        sys.exit(1)

    data = cargar_json(args.archivo)

    if args.keys:
        if not isinstance(data, dict):
            print("Error: el JSON del nivel superior no es un objeto", file=sys.stderr)
            sys.exit(1)
        for clave in data.keys():
            print(clave)

    elif args.get:
        valor = obtener_valor(data, args.get)
        print(json.dumps(valor, ensure_ascii=False))

    elif args.pretty:
        print(json.dumps(data, indent=4, ensure_ascii=False))

    elif args.set:
        clave, valor = args.set
        nuevo_valor = convertir_valor(valor)
        setear_valor(data, clave, nuevo_valor)
        guardar_json(data, args.output)

        if args.output != "-":
            print(f"Guardado en {args.output}")


if __name__ == "__main__":
    main()