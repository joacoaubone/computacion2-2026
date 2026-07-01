import time

import procfs


def agregador_loop(snapshot, shutdown_event, intervalo):
    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        datos = {}
        for pid in pids:
            status = procfs.leer_status(pid)
            if status is None:
                continue
            stat = procfs.leer_stat(pid)
            cmdline = procfs.leer_cmdline(pid)
            datos[pid] = {
                'status': status,
                'stat': stat,
                'cmdline': cmdline,
            }
        snapshot['datos'] = datos
        snapshot['agregador_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
