import os
import stat
import pwd
import grp
from pathlib import Path
import sys
from datetime import datetime

def obtener_tipo(modo):
    if stat.S_ISREG(modo):
        return "Archivo regular"
    elif stat.S_ISDIR(modo):
        return "Directorio"
    elif stat.S_ISLNK(modo):
        return "Enlace simbólico"
    elif stat.S_ISCHR(modo):
        return "Dispositivo de caracteres"
    elif stat.S_ISBLK(modo):
        return "Dispositivo de bloques"
    else:
        return "Otro"

def permisos_letra(modo):
    return stat.filemode(modo)

def permisos_numericos(modo):
    return oct(modo & 0o777)[2:]

def obtener_usuario(uid):
    return pwd.getpwuid(uid).pw_name

def obtener_grupo(gid):
    return grp.getgrgid(gid).gr_name

def tamaño_legible(bytes):
    for unidad in ["B", "KB", "MB", "GB", "TB"]:
        if bytes < 1024:
            return f"{bytes:.2f} {unidad}"
        bytes /= 1024
    return f"{bytes:.2f} PB"


def formatear_fecha(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def main():
    if len(sys.argv) != 2:
        print("Uso: inspector.py <ruta>")
        sys.exit(1)

    ruta = Path(sys.argv[1])

    if not ruta.exists() and not ruta.is_symlink():
        print(f"Error: la ruta '{ruta}' no existe")
        sys.exit(1)

    info = ruta.lstat()

    print(f"Archivo: {ruta}")
    print(f"Tipo: {obtener_tipo(info.st_mode)}")
    print(f"Tamaño: {info.st_size} bytes ({tamaño_legible(info.st_size)})")
    print(f"Permisos: {permisos_letra(info.st_mode)} ({permisos_numericos(info.st_mode)})")
    print(f"Propietario: {obtener_usuario(info.st_uid)} (uid: {info.st_uid})")
    print(f"Grupo: {obtener_grupo(info.st_gid)} (gid: {info.st_gid})")
    print(f"Inodo: {info.st_ino}")
    print(f"Enlaces duros: {info.st_nlink}")

    print(f"Cambio (ctime): {formatear_fecha(info.st_ctime)}")
    print(f"Última modificación: {formatear_fecha(info.st_mtime)}")
    print(f"Último acceso: {formatear_fecha(info.st_atime)}")

    if ruta.is_symlink():
        destino = os.readlink(ruta)
        print(f"-> Apunta a: {destino}")

    if ruta.is_dir():
        cantidad = len(list(ruta.iterdir()))
        print(f"Contenido: {cantidad} elementos")

if __name__ == "__main__":
    main()