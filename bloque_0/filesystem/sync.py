from pathlib import Path
import argparse
import shutil
import sys
import fnmatch
from datetime import datetime


def parse_excludes(exclude_str):
    """Convierte una cadena de patrones separados por coma en una lista."""
    if not exclude_str:
        return []
    return [pat.strip() for pat in exclude_str.split(",")]


def esta_excluido(path, patrones):
    """Verifica si un archivo o directorio está excluido según los patrones dados."""
    for patron in patrones:
        if fnmatch.fnmatch(path.name, patron):
            return True
    return False


def tamano_legible(size):
    """Convierte un tamaño en bytes a una representación legible."""
    size = float(size)
    for unidad in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unidad}"
        size /= 1024
    return f"{size:.1f} PB"


def formatear_fecha(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def obtener_archivos(base, patrones):
    archivos = {}

    for item in base.rglob("*"):
        try:
            if esta_excluido(item, patrones):
                continue

            if item.is_file():
                relativa = item.relative_to(base)
                archivos[str(relativa)] = item
        except (PermissionError, FileNotFoundError):
            continue

    return archivos


def analizar_cambios(origen, destino, patrones, delete_extra):
    archivos_origen = obtener_archivos(origen, patrones)
    archivos_destino = obtener_archivos(destino, patrones)

    rutas_origen = set(archivos_origen.keys())
    rutas_destino = set(archivos_destino.keys())

    nuevos = []
    modificados = []
    eliminados = []

    for ruta_relativa in sorted(rutas_origen):
        origen_path = archivos_origen[ruta_relativa]
        destino_path = destino / ruta_relativa

        try:
            if ruta_relativa not in rutas_destino:
                nuevos.append((ruta_relativa, origen_path.stat().st_size))
            else:
                stat_origen = origen_path.stat()
                stat_destino = destino_path.stat()

                if (
                    stat_origen.st_size != stat_destino.st_size
                    or stat_origen.st_mtime != stat_destino.st_mtime
                ):
                    modificados.append((ruta_relativa, stat_origen.st_mtime))
        except (PermissionError, FileNotFoundError):
            continue

    if delete_extra:
        for ruta_relativa in sorted(rutas_destino - rutas_origen):
            eliminados.append(ruta_relativa)

    return nuevos, modificados, eliminados


def mostrar_cambios(nuevos, modificados, eliminados):
    print("Cambios detectados:")

    for ruta, size in nuevos:
        print(f"  NUEVO:      {ruta} ({tamano_legible(size)})")

    for ruta, mtime in modificados:
        print(f"  MODIFICADO: {ruta} (cambiado {formatear_fecha(mtime)})")

    for ruta in eliminados:
        print(f"  ELIMINADO:  {ruta} (existe en destino pero no en origen)")

    print()
    print(
        f"Resumen: {len(nuevos)} nuevos, "
        f"{len(modificados)} modificados, "
        f"{len(eliminados)} eliminados"
    )


def copiar_archivo(origen_path, destino_path):
    destino_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen_path, destino_path)


def aplicar_cambios(origen, destino, nuevos, modificados, eliminados):
    for ruta, _ in nuevos:
        origen_path = origen / ruta
        destino_path = destino / ruta
        try:
            print(f"Copiando {ruta}...", end=" ")
            copiar_archivo(origen_path, destino_path)
            print("OK")
        except OSError as e:
            print(f"ERROR: {e}")

    for ruta, _ in modificados:
        origen_path = origen / ruta
        destino_path = destino / ruta
        try:
            print(f"Actualizando {ruta}...", end=" ")
            copiar_archivo(origen_path, destino_path)
            print("OK")
        except OSError as e:
            print(f"ERROR: {e}")

    for ruta in eliminados:
        destino_path = destino / ruta
        try:
            print(f"Eliminando {ruta}...", end=" ")
            destino_path.unlink()
            print("OK")
        except OSError as e:
            print(f"ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Sincroniza dos directorios."
    )
    parser.add_argument("origen", help="Directorio origen")
    parser.add_argument("destino", help="Directorio destino")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué haría sin ejecutar cambios"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Eliminar archivos extra en destino"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        help="Patrones a excluir, separados por coma"
    )

    args = parser.parse_args()

    origen = Path(args.origen)
    destino = Path(args.destino)

    if not origen.exists():
        print(f"Error: '{origen}' no existe")
        sys.exit(1)

    if not origen.is_dir():
        print(f"Error: '{origen}' no es un directorio")
        sys.exit(1)

    if not destino.exists():
        print(f"Error: '{destino}' no existe")
        sys.exit(1)

    if not destino.is_dir():
        print(f"Error: '{destino}' no es un directorio")
        sys.exit(1)

    patrones = parse_excludes(args.exclude)

    print("Analizando diferencias...\n")

    nuevos, modificados, eliminados = analizar_cambios(
        origen, destino, patrones, args.delete
    )

    mostrar_cambios(nuevos, modificados, eliminados)

    if args.dry_run:
        return

    if not nuevos and not modificados and not eliminados:
        print("\nNo hay cambios para sincronizar.")
        return

    respuesta = input("\n¿Proceder con la sincronización? [si/no] ")

    if respuesta.lower() == "no":
        print("Operación cancelada.")
        return

    print()
    aplicar_cambios(origen, destino, nuevos, modificados, eliminados)
    print("Completado.")


if __name__ == "__main__":
    main()