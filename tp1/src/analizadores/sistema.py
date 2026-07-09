import time

import procfs


def sistema_loop(snapshot, shutdown_event, intervalo):
    prev_cpu = None
    prev_total = 0

    while not shutdown_event.is_set():
        resumen = snapshot.get('resumen', {})
        memoria = snapshot.get('memoria', {})

        stat_sys = procfs.leer_stat_sistema()
        cpu_delta = {}
        if stat_sys and 'cpu' in stat_sys:
            c = stat_sys['cpu']
            total = c['user'] + c['nice'] + c['system'] + c['idle'] + c['iowait']
            if prev_cpu is not None:
                dt = total - prev_total
                if dt > 0:
                    cpu_delta = {
                        'user': round((c['user'] - prev_cpu['user']) / dt * 100, 1),
                        'system': round((c['system'] - prev_cpu['system']) / dt * 100, 1),
                        'idle': round((c['idle'] - prev_cpu['idle']) / dt * 100, 1),
                        'iowait': round((c['iowait'] - prev_cpu['iowait']) / dt * 100, 1),
                    }
            prev_cpu = c
            prev_total = total

        top_cpu = sorted(
            resumen.items(),
            key=lambda x: x[1].get('cpu_percent', 0),
            reverse=True,
        )[:5]

        top_mem = sorted(
            resumen.items(),
            key=lambda x: memoria.get(x[0], {}).get('rss', 0),
            reverse=True,
        )[:5]

        datos = {
            'cpu': cpu_delta,
            'meminfo': procfs.leer_meminfo(),
            'loadavg': procfs.leer_loadavg(),
            'uptime': procfs.leer_uptime(),
            'stat_sys': stat_sys,
            'top_cpu': [
                {'pid': p, 'name': d.get('name', '?'), 'cpu': d.get('cpu_percent', 0)}
                for p, d in top_cpu
            ],
            'top_mem': [
                {'pid': p, 'name': resumen.get(p, {}).get('name', '?'), 'rss': memoria.get(p, {}).get('rss', 0)}
                for p, _ in top_mem
            ],
        }

        snapshot['sistema'] = datos
        snapshot['sistema_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
