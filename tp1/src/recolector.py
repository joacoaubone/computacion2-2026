import time
import procfs

def recolector_loop(snapshot, shutdown_event, intervalo):
    while not shutdown_event.is_set():
        try:
            pids = procfs.listar_pids()
            snapshot['pids'] = pids
            snapshot['recolector_ts'] = time.time()
        except Exception:
            pass
        shutdown_event.wait(timeout=intervalo.value)
