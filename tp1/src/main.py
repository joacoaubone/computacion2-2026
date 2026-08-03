import json
import multiprocessing
import os
import shutil
import signal
import time

from rich.live import Live
from rich.panel import Panel

from keyboard import entrar_modo_raw, salir_modo_raw, leer_tecla
from senales import setup_señales, recibir_señales
from recolector import recolector_loop
from analizadores.resumen import resumen_loop
from analizadores.memoria import memoria_loop
from analizadores.sistema import sistema_loop
from analizadores.fds import fds_loop
from analizadores.threads import threads_loop
from analizadores.senales import senales_loop
from analizadores.scheduling import scheduling_loop
from display import (
    crear_layout, render_header,
    render_tabla_procesos,
    render_hint, render_vista_memoria,
    render_vista_fds, render_vista_threads,
    render_vista_senales, render_vista_scheduling,
    render_vista_sistema, render_detalle,
    render_footer, render_ayuda,
)


CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

VIEW_MAP = {'r': 1, 'm': 2, 'f': 3, 't': 4, 's': 5, 'p': 6, 'g': 7}

VIEW_INTERVAL = {
    1: 'resumen', 2: 'memoria', 3: 'fds', 4: 'threads',
    5: 'senales', 6: 'scheduling', 7: 'sistema',
}

VIEW_MIN = {
    'resumen': 0.5, 'memoria': 1.0, 'fds': 2.0, 'threads': 0.5,
    'senales': 5.0, 'scheduling': 5.0, 'sistema': 1.0,
}


def cargar_config(intervalos):
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        for nombre, valor in config.get('intervalos', {}).items():
            if nombre in intervalos:
                min_iv = VIEW_MIN.get(nombre, 0.5)
                intervalos[nombre].value = max(valor, min_iv)
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def dump_snapshot(snapshot):
    timestamp = int(time.time())
    path = os.path.join(os.path.dirname(__file__), '..', f'dump_{timestamp}.json')
    data = dict(snapshot)
    for k, v in data.items():
        if hasattr(v, 'items'):
            data[k] = dict(v)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def despachar_señal(senal, intervalos, snapshot):
    if senal is None:
        return 'ok'
    if senal in (signal.SIGINT, signal.SIGTERM):
        return 'salir'
    if senal == signal.SIGHUP:
        cargar_config(intervalos)
        return 'ok'
    if senal == signal.SIGUSR1:
        dump_snapshot(snapshot)
        return 'ok'
    if senal == signal.SIGUSR2:
        return 'verbose'
    return 'ok'


def main():
    with multiprocessing.Manager() as manager:
        snapshot = manager.dict()
        shutdown_event = multiprocessing.Event()

        intervalos = {
            'recolector': multiprocessing.Value('d', 2.0),
            'resumen': multiprocessing.Value('d', 2.0),
            'memoria': multiprocessing.Value('d', 3.0),
            'sistema': multiprocessing.Value('d', 2.0),
            'fds': multiprocessing.Value('d', 5.0),
            'threads': multiprocessing.Value('d', 2.0),
            'senales': multiprocessing.Value('d', 10.0),
            'scheduling': multiprocessing.Value('d', 10.0),
        }

        specs = [
            (recolector_loop, (snapshot, shutdown_event, intervalos['recolector'])),
            (resumen_loop, (snapshot, shutdown_event, intervalos['resumen'])),
            (memoria_loop, (snapshot, shutdown_event, intervalos['memoria'])),
            (sistema_loop, (snapshot, shutdown_event, intervalos['sistema'])),
            (fds_loop, (snapshot, shutdown_event, intervalos['fds'])),
            (threads_loop, (snapshot, shutdown_event, intervalos['threads'])),
            (senales_loop, (snapshot, shutdown_event, intervalos['senales'])),
            (scheduling_loop, (snapshot, shutdown_event, intervalos['scheduling'])),
        ]

        procesos = [multiprocessing.Process(target=t, args=a) for t, a in specs]

        for p in procesos:
            p.start()

        cargar_config(intervalos)

        selected_idx = 0
        scroll_offset = 0
        active_view = 1
        sort_mode = 0
        filter_cmd = ''
        filter_mode = False
        filter_text = ''
        filter_user_mode = False
        filter_user_text = ''
        filter_uid = ''
        detalle_pid = None
        ayuda_mode = False
        verbose_mode = False

        layout = crear_layout()
        setup_señales()
        entrar_modo_raw()

        try:
            with Live(layout, refresh_per_second=4, screen=True) as live:
                items = []
                while not shutdown_event.is_set():
                    pids = snapshot.get('pids', [])
                    rows = shutil.get_terminal_size().lines
                    region_h = max((rows - 6) * 3 // 5, 3)
                    overhead = 2 if active_view == 1 else 4
                    max_rows = max(region_h - overhead, 1)

                    # === SCROLL: la ventana sigue al cursor (items del frame anterior) ===
                    if selected_idx < scroll_offset:
                        scroll_offset = selected_idx
                    if items and selected_idx >= scroll_offset + max_rows:
                        scroll_offset = selected_idx - max_rows + 1

                    resumen = snapshot.get('resumen', {})
                    memoria = snapshot.get('memoria', {})

                    # === TABLA SUPERIOR: cambia según vista activa ===
                    if active_view == 7:
                        tabla_renderable = render_vista_sistema(
                            snapshot.get('sistema', {}),
                        )
                        items = []
                    elif active_view == 1:
                        tabla_renderable, items = render_tabla_procesos(
                            resumen, memoria, selected_idx, sort_mode,
                            filter_cmd, scroll_offset, max_rows, filter_uid,
                        )
                    elif active_view == 2:
                        tabla_renderable, items = render_vista_memoria(
                            resumen, memoria, selected_idx, scroll_offset, max_rows,
                            filter_uid, filter_cmd,
                        )
                    elif active_view == 3:
                        tabla_renderable, items = render_vista_fds(
                            resumen, snapshot.get('fds', {}),
                            selected_idx, scroll_offset, max_rows,
                            filter_uid, filter_cmd,
                        )
                    elif active_view == 4:
                        tabla_renderable, items = render_vista_threads(
                            resumen, snapshot.get('threads', {}),
                            selected_idx, scroll_offset, max_rows,
                            filter_uid, filter_cmd,
                        )
                    elif active_view == 5:
                        tabla_renderable, items = render_vista_senales(
                            resumen, snapshot.get('senales', {}),
                            selected_idx, scroll_offset, max_rows,
                            filter_uid, filter_cmd,
                        )
                    else:
                        tabla_renderable, items = render_vista_scheduling(
                            resumen, snapshot.get('scheduling', {}),
                            selected_idx, scroll_offset, max_rows,
                            filter_uid, filter_cmd,
                        )

                    # === SELECCION ===
                    if items:
                        selected_idx = min(selected_idx, len(items) - 1)
                    else:
                        selected_idx = 0

                    # === PANEL INFERIOR ===
                    if ayuda_mode:
                        layout['header'].update(render_header(
                            len(pids), active_view,
                            'VERBOSE' if verbose_mode else '',
                        ))
                        layout['table'].update(tabla_renderable)
                        layout['detail'].update(render_ayuda())
                        layout['footer'].update(
                            Panel('Enter/Esc: volver', style='bold white on blue')
                        )
                        live.refresh()
                        tecla = leer_tecla(0.25)
                        accion = despachar_señal(
                            recibir_señales(0), intervalos, snapshot)
                        if accion == 'salir':
                            break
                        elif accion == 'verbose':
                            verbose_mode = not verbose_mode
                        if tecla == 'KEY_CTRLC':
                            break
                        if tecla in ('KEY_ENTER', 'ESC', 'q', 'h', '?'):
                            ayuda_mode = False
                        continue

                    if detalle_pid is not None:
                        layout['header'].update(render_header(
                            len(pids), active_view,
                            'VERBOSE' if verbose_mode else '',
                        ))
                        layout['table'].update(tabla_renderable)
                        layout['detail'].update(render_detalle(
                            detalle_pid,
                            snapshot.get('resumen', {}),
                            snapshot.get('memoria', {}),
                            snapshot.get('fds', {}),
                            snapshot.get('threads', {}),
                            snapshot.get('senales', {}),
                            snapshot.get('scheduling', {}),
                            verbose_mode,
                        ))
                        layout['footer'].update(
                            Panel('Enter/Esc/q: volver', style='bold white on blue')
                        )
                        live.refresh()
                        tecla = leer_tecla(0.25)
                        accion = despachar_señal(
                            recibir_señales(0), intervalos, snapshot)
                        if accion == 'salir':
                            break
                        elif accion == 'verbose':
                            verbose_mode = not verbose_mode
                        if tecla == 'KEY_CTRLC':
                            break
                        if tecla in ('KEY_ENTER', 'ESC', 'q'):
                            detalle_pid = None
                        continue

                    # === VISTA NORMAL: abajo siempre hint ===
                    detail_renderable = render_hint()

                    layout['header'].update(render_header(
                        len(pids), active_view,
                        'VERBOSE' if verbose_mode else '',
                    ))
                    layout['table'].update(tabla_renderable)
                    layout['detail'].update(detail_renderable)
                    iv_key = VIEW_INTERVAL.get(active_view, 'resumen')
                    iv_actual = intervalos[iv_key].value if iv_key in intervalos else 2.0
                    layout['footer'].update(render_footer(
                        filter_cmd, sort_mode, iv_actual,
                        filter_mode, filter_text,
                        filter_user_mode, filter_user_text,
                        filter_uid, verbose_mode,
                    ))
                    live.refresh()

                    tecla = leer_tecla(0.25)

                    senal = recibir_señales(0)
                    accion = despachar_señal(senal, intervalos, snapshot)
                    if accion == 'salir':
                        break
                    elif accion == 'verbose':
                        verbose_mode = not verbose_mode

                    if filter_mode:
                        if tecla is None:
                            continue
                        if tecla == 'KEY_ENTER':
                            filter_cmd = filter_text
                            filter_mode = False
                            filter_text = ''
                            selected_idx = 0
                            scroll_offset = 0
                            continue
                        if tecla == 'ESC':
                            filter_mode = False
                            filter_text = ''
                            continue
                        if tecla == 'KEY_BACKSPACE':
                            filter_text = filter_text[:-1]
                            continue
                        if isinstance(tecla, str) and len(tecla) == 1:
                            filter_text += tecla
                        continue

                    if filter_user_mode:
                        if tecla is None:
                            continue
                        if tecla == 'KEY_ENTER':
                            filter_uid = filter_user_text
                            filter_user_mode = False
                            filter_user_text = ''
                            selected_idx = 0
                            scroll_offset = 0
                            continue
                        if tecla == 'ESC':
                            filter_user_mode = False
                            filter_user_text = ''
                            continue
                        if tecla == 'KEY_BACKSPACE':
                            filter_user_text = filter_user_text[:-1]
                            continue
                        if isinstance(tecla, str) and len(tecla) == 1:
                            filter_user_text += tecla
                        continue

                    if tecla is None:
                        continue
                    if tecla == 'q':
                        break
                    if tecla == 'KEY_UP':
                        if items and selected_idx > 0:
                            selected_idx -= 1
                    elif tecla == 'KEY_DOWN':
                        if items:
                            max_idx = len(items) - 1
                            if selected_idx < max_idx:
                                selected_idx += 1
                    elif tecla == 'KEY_ENTER':
                        if items and selected_idx < len(items):
                            detalle_pid = items[selected_idx][0]
                    elif tecla in ('1', '2', '3', '4', '5', '6', '7'):
                        active_view = int(tecla)
                        selected_idx = 0
                        scroll_offset = 0
                    elif tecla in VIEW_MAP:
                        active_view = VIEW_MAP[tecla]
                        selected_idx = 0
                        scroll_offset = 0
                    elif tecla == '/':
                        filter_mode = True
                        filter_text = ''
                    elif tecla == 'u':
                        filter_user_mode = True
                        filter_user_text = ''
                    elif tecla == 'c':
                        sort_mode = (sort_mode + 1) % 3
                        selected_idx = 0
                        scroll_offset = 0
                    elif tecla == '+':
                        iv_key = VIEW_INTERVAL.get(active_view)
                        if iv_key and iv_key in intervalos:
                            intervalos[iv_key].value = min(intervalos[iv_key].value + 0.5, 10.0)
                    elif tecla == '-':
                        iv_key = VIEW_INTERVAL.get(active_view)
                        if iv_key and iv_key in intervalos:
                            min_iv = VIEW_MIN.get(iv_key, 0.5)
                            intervalos[iv_key].value = max(intervalos[iv_key].value - 0.5, min_iv)
                    elif tecla in ('h', '?'):
                        ayuda_mode = True
                    elif tecla == 'KEY_CTRLC':
                        break

        except KeyboardInterrupt:
            pass
        finally:
            salir_modo_raw()
            shutdown_event.set()
            for p in procesos:
                p.join(timeout=11)


if __name__ == '__main__':
    main()
