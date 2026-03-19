import argparse
import json
import sys
from pathlib import Path

ARCHIVO_TAREAS = Path.home() / ".tareas.json"


def cargar_tareas():
    """Carga las tareas desde el archivo JSON."""
    if not ARCHIVO_TAREAS.exists():
        return []

    try:
        with open(ARCHIVO_TAREAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("Error: el archivo de tareas está corrupto", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error al leer tareas: {e}", file=sys.stderr)
        sys.exit(1)


def guardar_tareas(tareas):
    """Guarda las tareas en el archivo JSON."""
    try:
        with open(ARCHIVO_TAREAS, "w", encoding="utf-8") as f:
            json.dump(tareas, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar tareas: {e}", file=sys.stderr)
        sys.exit(1)


def siguiente_id(tareas):
    """Devuelve el siguiente ID disponible."""
    if not tareas:
        return 1
    return max(t["id"] for t in tareas) + 1


def buscar_tarea_por_id(tareas, tarea_id):
    """Busca una tarea por ID."""
    for tarea in tareas:
        if tarea["id"] == tarea_id:
            return tarea
    return None


def comando_add(args):
    tareas = cargar_tareas()

    nueva_tarea = {
        "id": siguiente_id(tareas),
        "descripcion": args.descripcion,
        "completada": False,
        "priority": args.priority
    }

    tareas.append(nueva_tarea)
    guardar_tareas(tareas)

    if args.priority:
        print(f"Tarea #{nueva_tarea['id']} agregada (prioridad: {args.priority})")
    else:
        print(f"Tarea #{nueva_tarea['id']} agregada")


def comando_list(args):
    tareas = cargar_tareas()

    resultado = tareas

    if args.pending:
        resultado = [t for t in resultado if not t["completada"]]

    if args.done:
        resultado = [t for t in resultado if t["completada"]]

    if args.priority:
        resultado = [t for t in resultado if t["priority"] == args.priority]

    for tarea in resultado:
        estado = "x" if tarea["completada"] else " "
        linea = f"#{tarea['id']} [{estado}] {tarea['descripcion']}"

        if tarea["priority"]:
            linea += f" [{tarea['priority'].upper()}]"

        print(linea)


def comando_done(args):
    tareas = cargar_tareas()
    tarea = buscar_tarea_por_id(tareas, args.id)

    if tarea is None:
        print(f"Error: no existe la tarea #{args.id}", file=sys.stderr)
        sys.exit(1)

    tarea["completada"] = True
    guardar_tareas(tareas)

    print(f"Tarea #{args.id} completada")


def comando_remove(args):
    tareas = cargar_tareas()
    tarea = buscar_tarea_por_id(tareas, args.id)

    if tarea is None:
        print(f"Error: no existe la tarea #{args.id}", file=sys.stderr)
        sys.exit(1)

    respuesta = input(f'¿Eliminar "{tarea["descripcion"]}"? [s/N] ')

    if respuesta.lower() != "s":
        print("Operación cancelada")
        return

    tareas = [t for t in tareas if t["id"] != args.id]
    guardar_tareas(tareas)

    print(f"Tarea #{args.id} eliminada")


def crear_parser():
    parser = argparse.ArgumentParser(description="Gestor de tareas con subcomandos")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    # add
    parser_add = subparsers.add_parser("add", help="Agregar una tarea")
    parser_add.add_argument("descripcion", help="Descripción de la tarea")
    parser_add.add_argument(
        "--priority",
        choices=["baja", "media", "alta"],
        help="Prioridad de la tarea"
    )
    parser_add.set_defaults(func=comando_add)

    # list
    parser_list = subparsers.add_parser("list", help="Listar tareas")
    parser_list.add_argument(
        "--pending",
        action="store_true",
        help="Mostrar solo tareas pendientes"
    )
    parser_list.add_argument(
        "--done",
        action="store_true",
        help="Mostrar solo tareas completadas"
    )
    parser_list.add_argument(
        "--priority",
        choices=["baja", "media", "alta"],
        help="Filtrar por prioridad"
    )
    parser_list.set_defaults(func=comando_list)

    # done
    parser_done = subparsers.add_parser("done", help="Marcar tarea como completada")
    parser_done.add_argument("id", type=int, help="ID de la tarea")
    parser_done.set_defaults(func=comando_done)

    # remove
    parser_remove = subparsers.add_parser("remove", help="Eliminar una tarea")
    parser_remove.add_argument("id", type=int, help="ID de la tarea")
    parser_remove.set_defaults(func=comando_remove)

    return parser


def main():
    parser = crear_parser()
    args = parser.parse_args()

    try:
        args.func(args)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nInterrumpido", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()