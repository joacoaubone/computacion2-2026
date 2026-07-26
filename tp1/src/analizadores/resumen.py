import time

import procfs


CLK_TCK = procfs.clk_tck()


def resumen_loop(snapshot, shutdown_event, intervalo):
    prev = {}

    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        now = time.time()
        datos = {}

        for pid in pids:
            status = procfs.leer_status(pid)
            if status is None:
                continue
            stat = procfs.leer_stat(pid)
            cmdline = procfs.leer_cmdline(pid)

            cpu = 0.0
            if stat:
                total = stat.get('utime', 0) + stat.get('stime', 0)
                if pid in prev:
                    dt = now - prev[pid]['time']
                    if dt > 0:
                        cpu = (total - prev[pid]['jiffies']) / CLK_TCK / dt * 100
                prev[pid] = {'jiffies': total, 'time': now}

            nombre = str(status.get('Name', '?'))
            uid_raw = str(status.get('Uid', '0'))
            gid_raw = str(status.get('Gid', '0'))
            uid = uid_raw.split()[0]
            gid = gid_raw.split()[0]
            group_name = procfs.resolver_gid(gid)
            datos[pid] = {
                'name': nombre,
                'state': stat.get('state', '?') if stat else '?',
                'ppid': stat.get('ppid', 0) if stat else 0,
                'uid': uid,
                'gid': gid,
                'group': group_name,
                'threads': stat.get('num_threads', 0) if stat else 0,
                'cpu_percent': round(cpu, 1),
                'cmdline': cmdline if cmdline else [],
            }

        for pid in list(prev.keys()):
            if pid not in datos:
                del prev[pid]

        snapshot['resumen'] = datos
        snapshot['resumen_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
