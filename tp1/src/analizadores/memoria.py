import time

import procfs


def memoria_loop(snapshot, shutdown_event, intervalo):
    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        datos = {}

        for pid in pids:
            status = procfs.leer_status(pid)
            if status is None:
                continue
            maps = procfs.leer_maps(pid)
            stat = procfs.leer_stat(pid)

            def v(val):
                if isinstance(val, str) and val.endswith(' kB'):
                    return int(val[:-3])
                return val if isinstance(val, (int, float)) else 0

            datos[pid] = {
                'rss': v(status.get('VmRSS', 0)),
                'vsize': v(status.get('VmSize', 0)),
                'data': v(status.get('VmData', 0)),
                'stack': v(status.get('VmStk', 0)),
                'exe': v(status.get('VmExe', 0)),
                'lib': v(status.get('VmLib', 0)),
                'swap': v(status.get('VmSwap', 0)),
                'hwm': v(status.get('VmHWM', 0)),
                'faults_min': stat.get('min_flt', 0) if stat else 0,
                'faults_maj': stat.get('maj_flt', 0) if stat else 0,
                'maps': maps,
            }

        snapshot['memoria'] = datos
        snapshot['memoria_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
