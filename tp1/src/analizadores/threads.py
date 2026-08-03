import time

import procfs


CLK_TCK = procfs.clk_tck()


def threads_loop(snapshot, shutdown_event, intervalo):
    prev = {}

    while not shutdown_event.is_set():
        try:
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
                        clave = (pid, tid)
                        if clave in prev:
                            dt = now - prev[clave]['time']
                            if dt > 0:
                                cpu = (total - prev[clave]['jiffies']) / CLK_TCK / dt * 100
                        prev[clave] = {'jiffies': total, 'time': now}

                    hilos.append({
                        'tid': tid,
                        'name': nombre,
                        'state': estado,
                        'cpu_percent': round(cpu, 1),
                        'ctxt_vol': info_status.get('voluntary_ctxt_switches', 0) if info_status else 0,
                        'ctxt_invol': info_status.get('nonvoluntary_ctxt_switches', 0) if info_status else 0,
                    })
                datos[pid] = hilos

            claves_vivas = set()
            for pid, hilos in datos.items():
                for h in hilos:
                    claves_vivas.add((pid, h['tid']))
            for clave in list(prev.keys()):
                if clave not in claves_vivas:
                    del prev[clave]

            snapshot['threads'] = datos
            snapshot['threads_ts'] = time.time()
        except Exception:
            pass
        shutdown_event.wait(timeout=intervalo.value)
