import time

import procfs


NOMBRES_SENIALES = [
    (0, 'SIGHUP'), (1, 'SIGINT'), (2, 'SIGQUIT'), (3, 'SIGILL'),
    (4, 'SIGTRAP'), (5, 'SIGABRT'), (6, 'SIGBUS'), (7, 'SIGFPE'),
    (8, 'SIGKILL'), (9, 'SIGUSR1'), (10, 'SIGSEGV'), (11, 'SIGUSR2'),
    (12, 'SIGPIPE'), (13, 'SIGALRM'), (14, 'SIGTERM'), (15, 'SIGSTKFLT'),
    (16, 'SIGCHLD'), (17, 'SIGCONT'), (18, 'SIGSTOP'), (19, 'SIGTSTP'),
    (20, 'SIGTTIN'), (21, 'SIGTTOU'), (22, 'SIGURG'), (23, 'SIGXCPU'),
    (24, 'SIGXFSZ'), (25, 'SIGVTALRM'), (26, 'SIGPROF'), (27, 'SIGWINCH'),
    (28, 'SIGIO'), (29, 'SIGPWR'), (30, 'SIGSYS'),
]


def decodificar_mascara(hex_str):
    try:
        mask = int(hex_str, 16)
    except (ValueError, TypeError):
        return []
    activas = []
    for bit, nombre in NOMBRES_SENIALES:
        if mask & (1 << bit): # ejemplo bit 3: 1<<3 = 8(2^3) = 0b1000
            activas.append(nombre)
    return activas


def senales_loop(snapshot, shutdown_event, intervalo):
    while not shutdown_event.is_set():
        pids = snapshot.get('pids', [])
        datos = {}

        for pid in pids:
            status = procfs.leer_status(pid)
            if status is None:
                continue
            datos[pid] = {
                'SigBlk': decodificar_mascara(status.get('SigBlk', '0')),
                'SigIgn': decodificar_mascara(status.get('SigIgn', '0')),
                'SigCgt': decodificar_mascara(status.get('SigCgt', '0')),
                'SigPnd': decodificar_mascara(status.get('SigPnd', '0')),
                'ShdPnd': decodificar_mascara(status.get('ShdPnd', '0')),
                'raw': {
                    'SigBlk': status.get('SigBlk', '0'),
                    'SigIgn': status.get('SigIgn', '0'),
                    'SigCgt': status.get('SigCgt', '0'),
                    'SigPnd': status.get('SigPnd', '0'),
                    'ShdPnd': status.get('ShdPnd', '0'),
                },
            }

        snapshot['senales'] = datos
        snapshot['senales_ts'] = time.time()
        shutdown_event.wait(timeout=intervalo.value)
