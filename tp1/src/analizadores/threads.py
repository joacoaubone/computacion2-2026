import time

import procfs


CLK_TCK = procfs.clk_tck()


def threads_loop(snapshot, shutdown_event, intervalo):
    prev = {}

    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        now = time.time()
        datos = {}

        for pid in pids:
            tids = procfs.listar_threads(pid)
            if tids is None:
                continue
            hilos = []
            for tid in tids:
                stat = procfs.leer_thread_stat(pid, tid)
                estado = stat.get('state', '?') if stat else '?'
                info_status = procfs.leer_thread_status(pid, tid)
                nombre = info_status.get('Name', '?') if info_status else '?'

                cpu = 0.0
                if stat:
                    total = stat.get('utime', 0) + stat.get('stime', 0)
                    if tid in prev:
                        dt = now - prev[tid]['time']
                        if dt > 0:
                            cpu = (total - prev[tid]['jiffies']) / CLK_TCK / dt * 100
                    prev[tid] = {'jiffies': total, 'time': now}

                hilos.append({
                    'tid': tid,
                    'name': nombre,
                    'state': estado,
                    'cpu_percent': round(cpu, 1),
                })
            datos[pid] = hilos

        tids_vivos = set()
        for hilos in datos.values():
            for h in hilos:
                tids_vivos.add(h['tid'])
        for tid in list(prev.keys()):
            if tid not in tids_vivos:
                del prev[tid]

        snapshot['threads'] = datos
        snapshot['threads_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
