import os

HEX_CAMPOS = {'SigBlk', 'SigIgn', 'SigCgt', 'SigPnd', 'ShdPnd',
              'CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'}


def clk_tck(): 
    """ Devuelve la cantidad de ticks por segundo del sistema, que es necesaria para convertir los tiempos de CPU en segundos. """
    return os.sysconf(os.sysconf_names['SC_CLK_TCK'])


def listar_pids(): 
    """ Devuelve una lista con los PIDs de todos los procesos en ejecución. """
    pids = []
    for entry in os.listdir('/proc'):
        if entry.isdigit():
            pids.append(int(entry))
    return sorted(pids)


def leer_status(pid):
    """ Devuelve un diccionario con la información del proceso obtenida del archivo /proc/[pid]/status. """
    try:
        with open(f'/proc/{pid}/status') as f:
            datos = {}
            for line in f:
                if ':' not in line:
                    continue
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()
                if value.isdigit() and key not in HEX_CAMPOS:
                    value = int(value)
                datos[key] = value
            return datos
    except (FileNotFoundError, PermissionError):
        return None


def leer_stat(pid):
    """ Devuelve un diccionario con la información del proceso obtenida del archivo /proc/[pid]/stat. """
    try:
        with open(f'/proc/{pid}/stat') as f:
            line = f.readline().strip()

        pid_end = line.find('(')
        _pid = int(line[:pid_end].strip())

        comm_start = pid_end + 1
        comm_end = line.rfind(')')
        comm = line[comm_start:comm_end]

        rest = line[comm_end + 2:].split()
        campos = ['pid', 'comm', 'state', 'ppid', 'pgid',
                  'sid', 'tty_nr', 'tty_pgrp', 'flags', 'min_flt',
                  'cmin_flt', 'maj_flt', 'cmaj_flt', 'utime', 'stime',
                  'cutime', 'cstime', 'priority', 'nice', 'num_threads',
                  'it_real_value', 'start_time', 'vsize', 'rss', 'rsslim',
                  'start_code', 'end_code', 'start_stack', 'kstk_esp', 'kstk_eip',
                  'signal', 'blocked', 'sigignore', 'sigcatch', 'wchan',
                  'nswap', 'cnswap', 'exit_signal', 'processor', 'rt_priority',
                  'policy', 'delayacct_blkio_ticks', 'guest_time', 'cguest_time',
                  'start_data', 'end_data', 'start_brk', 'arg_start', 'arg_end',
                  'env_start', 'env_end', 'exit_code']

        resultado = {'pid': _pid, 'comm': comm}
        for i, campo in enumerate(campos[2:], start=2):
            idx = i - 2
            if idx < len(rest):
                v = rest[idx]
                try:
                    resultado[campo] = int(v)
                except ValueError:
                    resultado[campo] = v
        return resultado
    except (FileNotFoundError, PermissionError):
        return None


def leer_cmdline(pid):
    """ Devuelve una lista con los argumentos de línea de comandos del proceso. """
    try:
        with open(f'/proc/{pid}/cmdline') as f:
            data = f.read()
            return data.split('\0')[:-1] if data else []
    except (FileNotFoundError, PermissionError):
        return None


def leer_meminfo():
    """ Devuelve un diccionario con la información de la memoria del sistema. """
    datos = {}
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                key, _, value = line.partition(':')
                value = value.strip()
                parts = value.split()
                if parts:
                    datos[key.strip()] = int(parts[0])
        return datos
    except FileNotFoundError:
        return None


def leer_loadavg():
    """ Devuelve un diccionario con la información de carga del sistema. """
    try:
        with open('/proc/loadavg') as f:
            parts = f.read().strip().split()
            return {
                'load_1min': float(parts[0]),
                'load_5min': float(parts[1]),
                'load_15min': float(parts[2]),
                'procs_running': int(parts[3].split('/')[0]),
                'procs_total': int(parts[3].split('/')[1]),
                'last_pid': int(parts[4]),
            }
    except FileNotFoundError:
        return None


def leer_stat_sistema():
    """ Devuelve un diccionario con la información del sistema obtenida del archivo /proc/stat. """
    datos = {}
    try:
        with open('/proc/stat') as f:
            for line in f:
                if line.startswith('cpu '):
                    parts = line.split()
                    datos['cpu'] = {
                        'user': int(parts[1]),
                        'nice': int(parts[2]),
                        'system': int(parts[3]),
                        'idle': int(parts[4]),
                        'iowait': int(parts[5]),
                    }
                elif line.startswith('btime '):
                    datos['btime'] = int(line.split()[1])
                elif line.startswith('ctxt '):
                    datos['ctxt'] = int(line.split()[1])
                elif line.startswith('processes '):
                    datos['processes'] = int(line.split()[1])
                elif line.startswith('procs_running '):
                    datos['procs_running'] = int(line.split()[1])
                elif line.startswith('procs_blocked '):
                    datos['procs_blocked'] = int(line.split()[1])
        return datos
    except FileNotFoundError:
        return None


def leer_uptime():
    """ Devuelve un diccionario con la información de tiempo de actividad del sistema. """
    try:
        with open('/proc/uptime') as f:
            parts = f.read().strip().split()
            return {
                'uptime': float(parts[0]),
                'idle': float(parts[1]),
            }
    except FileNotFoundError:
        return None


def listar_fds(pid):
    """ Devuelve una lista con los descriptores de archivo del proceso. """
    try:
        return sorted(int(fd) for fd in os.listdir(f'/proc/{pid}/fd'))
    except (FileNotFoundError, PermissionError):
        return None


def leer_fd_destino(pid, fd):
    """ Devuelve la ruta a la que apunta el descriptor de archivo. """
    try:
        return os.readlink(f'/proc/{pid}/fd/{fd}')
    except (FileNotFoundError, PermissionError):
        return None


def listar_threads(pid):
    """ Devuelve una lista con los identificadores de los hilos del proceso. """
    try:
        return sorted(int(t) for t in os.listdir(f'/proc/{pid}/task'))
    except (FileNotFoundError, PermissionError):
        return None


def leer_thread_status(pid, tid):
    """ Devuelve un diccionario con la información del hilo obtenida del archivo /proc/[pid]/task/[tid]/status. """
    if tid == pid:
        return leer_status(pid)
    try:
        datos = {}
        with open(f'/proc/{pid}/task/{tid}/status') as f:
            for line in f:
                if ':' not in line:
                    continue
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()
                if value.isdigit() and key not in HEX_CAMPOS:
                    value = int(value)
                datos[key] = value
        return datos
    except (FileNotFoundError, PermissionError):
        return None


def leer_thread_stat(pid, tid):
    """ Devuelve un diccionario con la información del hilo obtenida del archivo /proc/[pid]/task/[tid]/stat. """
    if tid == pid:
        return leer_stat(pid)
    try:
        with open(f'/proc/{pid}/task/{tid}/stat') as f:
            line = f.readline().strip()

        pid_end = line.find('(')
        _pid = int(line[:pid_end].strip())

        comm_start = pid_end + 1
        comm_end = line.rfind(')')
        comm = line[comm_start:comm_end]

        rest = line[comm_end + 2:].split()
        campos = ['pid', 'comm', 'state', 'ppid', 'pgid',
                  'sid', 'tty_nr', 'tty_pgrp', 'flags', 'min_flt',
                  'cmin_flt', 'maj_flt', 'cmaj_flt', 'utime', 'stime',
                  'cutime', 'cstime', 'priority', 'nice', 'num_threads',
                  'it_real_value', 'start_time', 'vsize', 'rss', 'rsslim',
                  'start_code', 'end_code', 'start_stack', 'kstk_esp', 'kstk_eip',
                  'signal', 'blocked', 'sigignore', 'sigcatch', 'wchan',
                  'nswap', 'cnswap', 'exit_signal', 'processor', 'rt_priority',
                  'policy', 'delayacct_blkio_ticks', 'guest_time', 'cguest_time',
                  'start_data', 'end_data', 'start_brk', 'arg_start', 'arg_end',
                  'env_start', 'env_end', 'exit_code']

        resultado = {'pid': _pid, 'comm': comm}
        for i, campo in enumerate(campos[2:], start=2):
            idx = i - 2
            if idx < len(rest):
                v = rest[idx]
                try:
                    resultado[campo] = int(v)
                except ValueError:
                    resultado[campo] = v
        return resultado
    except (FileNotFoundError, PermissionError):
        return None


def resolver_gid(gid):
    """Resuelve un GID numérico a nombre de grupo leyendo /etc/group."""
    try:
        gid_str = str(int(gid))
        with open('/etc/group') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 3 and parts[2] == gid_str:
                    return parts[0]
    except (ValueError, FileNotFoundError, PermissionError):
        pass
    return str(gid)


def resolver_uid(uid):
    """Resuelve un UID numérico a nombre de usuario leyendo /etc/passwd."""
    try:
        uid_str = str(int(uid))
        with open('/etc/passwd') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 3 and parts[2] == uid_str:
                    return parts[0]
    except (ValueError, FileNotFoundError, PermissionError):
        pass
    return str(uid)


def leer_maps(pid):
    """ Devuelve una lista de diccionarios con la información de las regiones de memoria del proceso obtenida del archivo /proc/[pid]/maps. """
    try:
        regiones = []
        with open(f'/proc/{pid}/maps') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                direcciones = parts[0]
                permisos = parts[1]
                offset = parts[2]
                path = parts[-1] if len(parts) >= 6 else ''

                addr_inicio, addr_fin = direcciones.split('-')
                regiones.append({
                    'inicio': int(addr_inicio, 16),
                    'fin': int(addr_fin, 16),
                    'perms': permisos,
                    'offset': offset,
                    'path': path,
                })
        return regiones
    except (FileNotFoundError, PermissionError):
        return None
