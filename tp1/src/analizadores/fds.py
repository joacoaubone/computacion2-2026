import time
import procfs


def _inferir_tipo(destino):
    if not destino or destino == '?':
        return '?'
    if 'socket:' in destino:
        return 'socket'
    if 'pipe:' in destino:
        return 'pipe'
    if 'tty' in destino or 'pts' in destino:
        return 'tty'
    if destino.startswith('/dev/'):
        return 'dev'
    return 'file'


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
                dest_str = destino if destino else '?'
                info.append({
                    'fd': fd,
                    'destino': dest_str,
                    'tipo': _inferir_tipo(dest_str),
                })
            datos[pid] = info

        snapshot['fds'] = datos
        snapshot['fds_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
