import multiprocessing
import shutil

from rich.live import Live
from rich.panel import Panel

from keyboard import entrar_modo_raw, salir_modo_raw, leer_tecla
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
    render_vista_resumen, render_vista_memoria,
    render_vista_fds, render_vista_threads,
    render_vista_senales, render_vista_scheduling,
    render_vista_sistema, render_detalle, render_footer,
)


def _dispatch_view(active_view, snapshot):
    resumen = snapshot.get('resumen', {})
    rows = shutil.get_terminal_size().lines
    max_rows = max(rows - 7, 3)

    if active_view == 1:
        memoria = snapshot.get('memoria', {})
        return render_vista_resumen(
            resumen, memoria, 0, 0, '',
            0, max_rows,
        )
    if active_view == 2:
        memoria = snapshot.get('memoria', {})
        return render_vista_memoria(resumen, memoria, 0, 0, max_rows)
    if active_view == 3:
        fds = snapshot.get('fds', {})
        return render_vista_fds(resumen, fds, 0, 0, max_rows)
    if active_view == 4:
        threads = snapshot.get('threads', {})
        return render_vista_threads(resumen, threads, 0, 0, max_rows)
    if active_view == 5:
        senales = snapshot.get('senales', {})
        return render_vista_senales(resumen, senales, 0, 0, max_rows)
    if active_view == 6:
        scheduling = snapshot.get('scheduling', {})
        return render_vista_scheduling(resumen, scheduling, 0, 0, max_rows)
    return None, []


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

        procesos = [
            multiprocessing.Process(
                target=recolector_loop,
                args=(snapshot, shutdown_event, intervalos['recolector']),
            ),
            multiprocessing.Process(
                target=resumen_loop,
                args=(snapshot, shutdown_event, intervalos['resumen']),
            ),
            multiprocessing.Process(
                target=memoria_loop,
                args=(snapshot, shutdown_event, intervalos['memoria']),
            ),
            multiprocessing.Process(
                target=sistema_loop,
                args=(snapshot, shutdown_event, intervalos['sistema']),
            ),
            multiprocessing.Process(
                target=fds_loop,
                args=(snapshot, shutdown_event, intervalos['fds']),
            ),
            multiprocessing.Process(
                target=threads_loop,
                args=(snapshot, shutdown_event, intervalos['threads']),
            ),
            multiprocessing.Process(
                target=senales_loop,
                args=(snapshot, shutdown_event, intervalos['senales']),
            ),
            multiprocessing.Process(
                target=scheduling_loop,
                args=(snapshot, shutdown_event, intervalos['scheduling']),
            ),
        ]

        for p in procesos:
            p.start()

        selected_idx = 0
        scroll_offset = 0
        active_view = 1
        sort_mode = 0
        filter_cmd = ''
        detalle_pid = None
        debug_tecla = ''

        layout = crear_layout()
        entrar_modo_raw()

        try:
            with Live(layout, refresh_per_second=4, screen=True) as live:
                while not shutdown_event.is_set():
                    pids = snapshot.get('pids', [])

                    if detalle_pid is not None:
                        main_renderable = render_detalle(
                            detalle_pid,
                            snapshot.get('resumen', {}),
                            snapshot.get('memoria', {}),
                            snapshot.get('fds', {}),
                            snapshot.get('threads', {}),
                            snapshot.get('senales', {}),
                            snapshot.get('scheduling', {}),
                        )
                        layout['header'].update(
                            render_header(len(pids), active_view, debug_tecla)
                        )
                        layout['main'].update(main_renderable)
                        layout['footer'].update(
                            Panel('Enter/Esc/q: volver', style='bold white on blue')
                        )
                        live.refresh()
                        tecla = leer_tecla(0.25)
                        if tecla in ('KEY_ENTER', 'ESC', 'q'):
                            detalle_pid = None
                        continue

                    rows = shutil.get_terminal_size().lines
                    max_rows = max(rows - 7, 3)

                    if active_view == 7:
                        sistema = snapshot.get('sistema', {})
                        main_renderable = render_vista_sistema(sistema)
                        items = []
                    else:
                        main_renderable, items = _dispatch_view(active_view, snapshot)

                    if items:
                        selected_idx = min(selected_idx, len(items) - 1)
                    else:
                        selected_idx = 0

                    if selected_idx < scroll_offset:
                        scroll_offset = selected_idx
                    if items and selected_idx >= scroll_offset + max_rows:
                        scroll_offset = selected_idx - max_rows + 1

                    if active_view == 1 and items:
                        memoria = snapshot.get('memoria', {})
                        main_renderable, _ = render_vista_resumen(
                            snapshot.get('resumen', {}), memoria,
                            selected_idx, sort_mode, filter_cmd,
                            scroll_offset, max_rows,
                        )
                    elif 2 <= active_view <= 6 and items:
                        resumen = snapshot.get('resumen', {})
                        if active_view == 2:
                            memoria = snapshot.get('memoria', {})
                            main_renderable, _ = render_vista_memoria(
                                resumen, memoria, selected_idx, scroll_offset, max_rows,
                            )
                        elif active_view == 3:
                            fds = snapshot.get('fds', {})
                            main_renderable, _ = render_vista_fds(
                                resumen, fds, selected_idx, scroll_offset, max_rows,
                            )
                        elif active_view == 4:
                            threads = snapshot.get('threads', {})
                            main_renderable, _ = render_vista_threads(
                                resumen, threads, selected_idx, scroll_offset, max_rows,
                            )
                        elif active_view == 5:
                            senales = snapshot.get('senales', {})
                            main_renderable, _ = render_vista_senales(
                                resumen, senales, selected_idx, scroll_offset, max_rows,
                            )
                        elif active_view == 6:
                            scheduling = snapshot.get('scheduling', {})
                            main_renderable, _ = render_vista_scheduling(
                                resumen, scheduling, selected_idx, scroll_offset, max_rows,
                            )

                    layout['header'].update(
                        render_header(len(pids), active_view, debug_tecla)
                    )
                    layout['main'].update(main_renderable)
                    layout['footer'].update(render_footer())
                    live.refresh()

                    tecla = leer_tecla(0.25)
                    if tecla is None:
                        continue
                    if tecla == 'q':
                        break
                    if tecla == 'KEY_UP':
                        if items and selected_idx > 0:
                            selected_idx -= 1
                        debug_tecla = ''
                    elif tecla == 'KEY_DOWN':
                        if items:
                            max_idx = len(items) - 1
                            if selected_idx < max_idx:
                                selected_idx += 1
                        debug_tecla = ''
                    elif tecla == 'KEY_ENTER':
                        if items and selected_idx < len(items):
                            pid = items[selected_idx][0]
                            detalle_pid = pid
                        debug_tecla = ''
                    elif tecla in ('1', '2', '3', '4', '5', '6', '7'):
                        active_view = int(tecla)
                        selected_idx = 0
                        scroll_offset = 0
                        debug_tecla = ''
                    elif tecla == 'ESC':
                        debug_tecla = ''
                    elif isinstance(tecla, str) and tecla.startswith('\x1b') and len(tecla) > 1:
                        debug_tecla = repr(tecla)[1:-1]
                    elif len(tecla) <= 2:
                        debug_tecla = repr(tecla)[1:-1]
                    else:
                        debug_tecla = ''

        except KeyboardInterrupt:
            pass
        finally:
            salir_modo_raw()
            shutdown_event.set()
            for p in procesos:
                p.join(timeout=3)


if __name__ == '__main__':
    main()
