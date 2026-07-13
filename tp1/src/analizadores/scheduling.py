import time

import procfs


POLICIES = {0: 'OTHER', 1: 'FIFO', 2: 'RR', 3: 'BATCH', 5: 'IDLE'}


def scheduling_loop(snapshot, shutdown_event, intervalo):
    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        datos = {}

        for pid in pids:
            status = procfs.leer_status(pid)
            if status is None:
                continue
            stat = procfs.leer_stat(pid)
            if stat is None:
                continue

            policy_num = stat.get('policy', 0)
            datos[pid] = {
                'nice': stat.get('nice', 0),
                'priority': stat.get('priority', 0),
                'policy': POLICIES.get(policy_num, str(policy_num)),
                'policy_num': policy_num,
                'rt_priority': stat.get('rt_priority', 0),
                'affinity': status.get('Cpus_allowed_list', '?'),
                'ctxt_vol': status.get('voluntary_ctxt_switches', 0),
                'ctxt_invol': status.get('nonvoluntary_ctxt_switches', 0),
                'sessid': stat.get('sid', 0),
                'pgid': stat.get('pgid', 0),
                'processor': stat.get('processor', 0),
            }

        snapshot['scheduling'] = datos
        snapshot['scheduling_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
