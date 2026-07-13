import time

import procfs


def fds_loop(snapshot, shutdown_event, intervalo):
    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        datos = {}

        for pid in pids:
            fds = procfs.listar_fds(pid)
            if fds is None:
                continue
            info = []
            for fd in fds:
                destino = procfs.leer_fd_destino(pid, fd)
                info.append({
                    'fd': fd,
                    'destino': destino if destino else '?',
                })
            datos[pid] = info

        snapshot['fds'] = datos
        snapshot['fds_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
