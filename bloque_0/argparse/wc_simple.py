import sys

if len(sys.argv) < 2:
    print("Error: Debe especificar un archivo")
    sys.exit(1)

nombre_archivo = sys.argv[1]

try:
    with open(nombre_archivo, "r") as f:
        lineas = 0
        for _ in f:
            lineas += 1

    print(f"{lineas} líneas")

except FileNotFoundError:
    print(f"Error: No se puede leer '{nombre_archivo}'")
    sys.exit(1)

except PermissionError:
    print(f"Error: No tiene permisos para leer '{nombre_archivo}'")
    sys.exit(1)

except Exception:
    print(f"Error: No se puede leer '{nombre_archivo}'")
    sys.exit(1)