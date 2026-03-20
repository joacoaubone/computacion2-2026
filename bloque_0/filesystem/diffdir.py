from pathlib import Path
import argparse
import hashlib
import sys
from datetime import datetime


def obtener_archivos(directorio, recursivo):
    """
    Devuelve un diccionario donde:
    clave   = ruta relativa
    valor   = Path absoluto
    """
    archivos = {}

    if recursivo:
        items = directorio.rglob("*")
    else:
        items = directorio.iterdir()

    for item in items:
        try:
            relativa = item.relative_to(directorio)
            archivos[str(relativa)] = item
        except (PermissionError, FileNotFoundError):
            continue

    return archivos


def calcular_hash(ruta):
    """
    Calcula el hash SHA256 de un archivo.
    """
    sha256 = hashlib.sha256()

    with open(ruta, "rb") as archivo:
        while True:
            bloque = archivo.read(8192)
            if not bloque:
                break
            sha256.update(bloque)

    return sha256.hexdigest()


def convertir_fecha(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def comparar_directorios(dir1, dir2, recursivo=False, checksum=False):
    elementos1 = obtener_archivos(dir1, recursivo)
    elementos2 = obtener_archivos(dir2, recursivo)

    rutas1 = set(elementos1.keys())
    rutas2 = set(elementos2.keys())

    solo_en_dir1 = sorted(rutas1 - rutas2)
    solo_en_dir2 = sorted(rutas2 - rutas1)
    en_ambos = sorted(rutas1 & rutas2)

    modificados_tamano = []
    modificados_fecha = []
    modificados_contenido = []
    identicos = 0

    for ruta_relativa in en_ambos:
        item1 = elementos1[ruta_relativa]
        item2 = elementos2[ruta_relativa]

        try:
            stat1 = item1.stat()
            stat2 = item2.stat()
        except (PermissionError, FileNotFoundError):
            continue

        if item1.is_dir() and item2.is_dir():
            identicos += 1
            continue

        if item1.is_file() and item2.is_file():
            if stat1.st_size != stat2.st_size:
                modificados_tamano.append(
                    (ruta_relativa, stat1.st_size, stat2.st_size)
                )
            elif checksum:
                try:
                    hash1 = calcular_hash(item1)
                    hash2 = calcular_hash(item2)

                    if hash1 != hash2:
                        modificados_contenido.append(ruta_relativa)
                    else:
                        identicos += 1
                except (PermissionError, FileNotFoundError):
                    continue
            elif stat1.st_mtime != stat2.st_mtime:
                modificados_fecha.append(
                    (
                        ruta_relativa,
                        convertir_fecha(stat1.st_mtime),
                        convertir_fecha(stat2.st_mtime),
                    )
                )
            else:
                identicos += 1

    return {
        "solo_en_dir1": solo_en_dir1,
        "solo_en_dir2": solo_en_dir2,
        "modificados_tamano": modificados_tamano,
        "modificados_fecha": modificados_fecha,
        "modificados_contenido": modificados_contenido,
        "identicos": identicos,
    }


def imprimir_resultados(dir1, dir2, resultados, checksum):
    print(f"Comparando {dir1} con {dir2}...\n")

    if resultados["solo_en_dir1"]:
        print(f"Solo en {dir1}:")
        for ruta in resultados["solo_en_dir1"]:
            print(f"  {ruta}")
        print()

    if resultados["solo_en_dir2"]:
        print(f"Solo en {dir2}:")
        for ruta in resultados["solo_en_dir2"]:
            print(f"  {ruta}")
        print()

    if resultados["modificados_tamano"]:
        print("Modificados (tamaño diferente):")
        for ruta, size1, size2 in resultados["modificados_tamano"]:
            print(f"  {ruta} ({size1} -> {size2} bytes)")
        print()

    if checksum and resultados["modificados_contenido"]:
        print("Modificados (contenido diferente - checksum):")
        for ruta in resultados["modificados_contenido"]:
            print(f"  {ruta}")
        print()

    if not checksum and resultados["modificados_fecha"]:
        print("Modificados (fecha diferente):")
        for ruta, fecha1, fecha2 in resultados["modificados_fecha"]:
            print(f"  {ruta} ({fecha1} -> {fecha2})")
        print()

    print(f"Idénticos: {resultados['identicos']} archivos/directorios")


def main():
    parser = argparse.ArgumentParser(
        description="Compara dos directorios."
    )

    parser.add_argument("dir1", help="Primer directorio")
    parser.add_argument("dir2", help="Segundo directorio")
    parser.add_argument(
        "--recursivo",
        action="store_true",
        help="Comparar también subdirectorios"
    )
    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Comparar contenido usando hash SHA256"
    )

    args = parser.parse_args()

    dir1 = Path(args.dir1)
    dir2 = Path(args.dir2)

    if not dir1.exists():
        print(f"Error: '{dir1}' no existe")
        sys.exit(1)

    if not dir2.exists():
        print(f"Error: '{dir2}' no existe")
        sys.exit(1)

    if not dir1.is_dir():
        print(f"Error: '{dir1}' no es un directorio")
        sys.exit(1)

    if not dir2.is_dir():
        print(f"Error: '{dir2}' no es un directorio")
        sys.exit(1)

    resultados = comparar_directorios(
        dir1,
        dir2,
        recursivo=args.recursivo,
        checksum=args.checksum
    )

    imprimir_resultados(dir1, dir2, resultados, args.checksum)


if __name__ == "__main__":
    main()