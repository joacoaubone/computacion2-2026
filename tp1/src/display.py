from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


NOMBRES_VISTA = {
    1: 'Resumen', 2: 'Memoria', 3: 'FDs', 4: 'Threads',
    5: 'Señales', 6: 'Scheduling', 7: 'Sistema',
}


def _matchea_filtro(resumen, pid, filter_cmd):
    """True si el proceso matchea el filtro '/': busca en el nombre completo
    y en la línea de comando (no en el nombre truncado a 16 chars)."""
    if not filter_cmd:
        return True
    d = resumen.get(pid, {})
    if not isinstance(d, dict):
        return False
    nombre = str(d.get('name', '?'))
    cmdline = d.get('cmdline', [])
    if not isinstance(cmdline, list):
        cmdline = []
    haystack = ' '.join([nombre] + [str(x) for x in cmdline]).lower()
    return filter_cmd.lower() in haystack


def _matchea_usuario(resumen, pid, filter_uid):
    """True si el proceso matchea el filtro 'u': busca como substring en el
    nombre de usuario (root, joaquin, ...) o en el UID numérico."""
    if not filter_uid:
        return True
    d = resumen.get(pid, {})
    if not isinstance(d, dict):
        return False
    return filter_uid in str(d.get('uid', '')) or filter_uid in str(d.get('user', ''))


def crear_layout():
    layout = Layout()
    layout.split_column(
        Layout(name='header', size=3),
        Layout(name='table', ratio=3),
        Layout(name='detail', ratio=2),
        Layout(name='footer', size=3),
    )
    return layout


def render_header(pids_count, active_view, debug_tecla=''):
    nombre = NOMBRES_VISTA.get(active_view, '?')
    texto = f'Monitor - PIDs: {pids_count}  Vista: [{active_view}] {nombre}'
    if debug_tecla:
        texto += f'  Tecla: {debug_tecla}'
    return Panel(texto, style='bold cyan')


def render_tabla_procesos(resumen, memoria, selected_idx, sort_mode,
                          filter_cmd, scroll_offset, max_rows, filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta', show_edge=False)
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('EST', width=3)
    table.add_column('CPU%', justify='right', width=5)
    table.add_column('RSS', justify='right', width=8)
    table.add_column('THR', justify='right', width=3)
    table.add_column('PPID', justify='right', width=7)
    table.add_column('USER', width=10)

    items = []
    for pid, d in resumen.items():
        if not _matchea_usuario(resumen, pid, filter_uid):
            continue
        if not _matchea_filtro(resumen, pid, filter_cmd):
            continue
        nombre = str(d.get('name', '?'))[:16]
        estado = d.get('state', '?')[:3]
        cpu = d.get('cpu_percent', 0.0)
        thr = d.get('threads', 0)
        ppid = d.get('ppid', 0)
        user = d.get('user', d.get('uid', '?'))
        m = memoria.get(pid, {})
        rss = m.get('rss', '?')
        items.append((pid, nombre, estado, cpu, rss, thr, ppid, user))

    if sort_mode == 0: # ordenar por CPU
        items.sort(key=lambda x: x[3], reverse=True)
    elif sort_mode == 1: # ordenar por RSS
        items.sort(key=lambda x: x[4] if isinstance(x[4], (int, float)) else 0, reverse=True)
    else: # ordenar por PID
        items.sort(key=lambda x: x[0]) 

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, estado, cpu, rss, thr, ppid, user = items[i]
        style = 'reverse' if i == selected_idx else ''
        cpu_str = f'{cpu:.1f}'
        rss_str = f'{rss:.0f}' if isinstance(rss, (int, float)) else str(rss)
        table.add_row(str(pid), nombre, estado, cpu_str, rss_str,
                      str(thr), str(ppid), str(user), style=style)

    return table, items


def render_hint():
    text = Text()
    text.append('\n\n')
    text.append('  Enter → Detalle del proceso seleccionado', style='dim')
    return Panel(text, title='[bold]Detalle[/]', border_style='blue')

def fmt(v):
    return f'{v:.0f}' if isinstance(v, (int, float)) else str(v)

def render_vista_memoria(resumen, memoria, selected_idx, scroll_offset, max_rows,
                         filter_uid='', filter_cmd=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('RSS', justify='right', width=8)
    table.add_column('VSIZE', justify='right', width=8)
    table.add_column('DATA', justify='right', width=8)
    table.add_column('STK', justify='right', width=7)
    table.add_column('EXE', justify='right', width=7)
    table.add_column('LIB', justify='right', width=7)
    table.add_column('HWM', justify='right', width=7)
    table.add_column('SWAP', justify='right', width=7)

    items = []
    for pid, d in memoria.items():
        if not _matchea_usuario(resumen, pid, filter_uid):
            continue
        if not _matchea_filtro(resumen, pid, filter_cmd):
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        rss = d.get('rss', 0)
        vsize = d.get('vsize', 0)
        data = d.get('data', 0)
        stack = d.get('stack', 0)
        exe = d.get('exe', 0)
        lib = d.get('lib', 0)
        hwm = d.get('hwm', 0)
        swap = d.get('swap', 0)
        items.append((pid, nombre, rss, vsize, data, stack, exe, lib, hwm, swap))

    items.sort(key=lambda x: x[2] if isinstance(x[2], (int, float)) else 0, reverse=True)

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, rss, vsize, data, stack, exe, lib, hwm, swap = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, fmt(rss), fmt(vsize), fmt(data),
                      fmt(stack), fmt(exe), fmt(lib), fmt(hwm), fmt(swap),
                      style=style)

    return table, items


def render_vista_fds(resumen, fds, selected_idx, scroll_offset, max_rows,
                     filter_uid='', filter_cmd=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('FDS', justify='right', width=4)
    table.add_column('TIPOS', width=30)

    items = []
    for pid, fds_list in fds.items():
        if not isinstance(fds_list, list):
            continue
        if not _matchea_usuario(resumen, pid, filter_uid):
            continue
        if not _matchea_filtro(resumen, pid, filter_cmd):
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        tipos = {}
        for fd_info in fds_list:
            t = fd_info.get('tipo', '?') if isinstance(fd_info, dict) else '?'
            tipos[t] = tipos.get(t, 0) + 1
        tipo_str = ' '.join(f'{t}:{c}' for t, c in sorted(tipos.items()))
        items.append((pid, nombre, len(fds_list), tipo_str))

    items.sort(key=lambda x: x[2], reverse=True)

    if not items:
        table.add_row('(sin datos)', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, count, tipo_str = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, str(count), tipo_str, style=style)

    return table, items


def render_vista_threads(resumen, threads, selected_idx, scroll_offset, max_rows,
                         filter_uid='', filter_cmd=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=20)
    table.add_column('THR', justify='right', width=5)
    table.add_column('CTX-V', justify='right', width=6)
    table.add_column('CTX-I', justify='right', width=6)
    table.add_column('DETALLE', width=30)

    items = []
    for pid, tids in threads.items():
        if not isinstance(tids, list):
            continue
        if not _matchea_usuario(resumen, pid, filter_uid):
            continue
        if not _matchea_filtro(resumen, pid, filter_cmd):
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:20]
        estados = {}
        total_vol = 0
        total_invol = 0
        for t in tids:
            s = t.get('state', '?')
            estados[s] = estados.get(s, 0) + 1
            total_vol += t.get('ctxt_vol', 0)
            total_invol += t.get('ctxt_invol', 0)
        detalle = ' '.join(f'{s}:{c}' for s, c in sorted(estados.items()))
        items.append((pid, nombre, len(tids), total_vol, total_invol, detalle))

    items.sort(key=lambda x: x[2], reverse=True)

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, count, vol, invol, detalle = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, str(count), str(vol), str(invol),
                      detalle[:30], style=style)

    return table, items


def render_vista_senales(resumen, senales, selected_idx, scroll_offset, max_rows,
                         filter_uid='', filter_cmd=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('Blk')
    table.add_column('Ign')
    table.add_column('Cgt')
    table.add_column('Pnd')
    table.add_column('ShdPnd')

    items = []
    for pid, d in senales.items():
        if not isinstance(d, dict):
            continue
        if not _matchea_usuario(resumen, pid, filter_uid):
            continue
        if not _matchea_filtro(resumen, pid, filter_cmd):
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        blk = ','.join(d.get('SigBlk', []))[:12]
        ign = ','.join(d.get('SigIgn', []))[:12]
        cgt = ','.join(d.get('SigCgt', []))[:12]
        pnd = ','.join(d.get('SigPnd', []))[:12]
        shdpnd = ','.join(d.get('ShdPnd', []))[:12]
        items.append((pid, nombre, blk, ign, cgt, pnd, shdpnd))

    items.sort(key=lambda x: x[0])

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, blk, ign, cgt, pnd, shdpnd = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, blk, ign, cgt, pnd, shdpnd, style=style)

    return table, items


def render_vista_scheduling(resumen, scheduling, selected_idx, scroll_offset, max_rows,
                            filter_uid='', filter_cmd=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', min_width=6)
    table.add_column('NOMBRE', min_width=6, max_width=16)
    table.add_column('NI', justify='right', min_width=3)
    table.add_column('PRI', justify='right', min_width=3)
    table.add_column('RT', justify='right', min_width=3)
    table.add_column('UT', justify='right', min_width=5)
    table.add_column('ST', justify='right', min_width=5)
    table.add_column('POLICY', min_width=4, max_width=6)
    table.add_column('AFF', min_width=4, max_width=8)
    table.add_column('SID', justify='right', min_width=6)
    table.add_column('PGID', justify='right', min_width=6)
    table.add_column('CTX-V', justify='right', min_width=5)
    table.add_column('CTX-I', justify='right', min_width=5)

    items = []
    for pid, d in scheduling.items():
        if not isinstance(d, dict):
            continue
        if not _matchea_usuario(resumen, pid, filter_uid):
            continue
        if not _matchea_filtro(resumen, pid, filter_cmd):
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        nice = d.get('nice', '?')
        pri = d.get('priority', '?')
        rt = d.get('rt_priority', 0)
        utime = d.get('utime', '?')
        stime = d.get('stime', '?')
        policy = str(d.get('policy', '?'))[:6]
        aff = str(d.get('affinity', '?'))[:8]
        sid = d.get('sessid', '?')
        pgid = d.get('pgid', '?')
        ctxt_vol = d.get('ctxt_vol', '?')
        ctxt_invol = d.get('ctxt_invol', '?')
        items.append((pid, nombre, nice, pri, rt, utime, stime,
                      policy, aff, sid, pgid, ctxt_vol, ctxt_invol))

    items.sort(key=lambda x: x[0])

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, nice, pri, rt, utime, stime, policy, aff, sid, pgid, ctxt_vol, ctxt_invol = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, str(nice), str(pri), str(rt), str(utime), str(stime),
                      policy, aff, str(sid), str(pgid), str(ctxt_vol), str(ctxt_invol), style=style)

    return table, items


def render_vista_sistema(sistema):
    text = Text()

    def section(titulo):
        text.append(f'\n── {titulo} ', style='bold cyan')
        text.append('─' * 50, style='dim')
        text.append('\n')

    def kv(key, val, val_style=''):
        text.append(f'  {key}: ', style='bold')
        if val_style:
            text.append(str(val), style=val_style)
        else:
            text.append(str(val))
        text.append('\n')

    section('CPU Global')
    cpu = sistema.get('cpu', {})
    if cpu:
        kv('User', f"{cpu.get('user', 0):.1f}%")
        kv('System', f"{cpu.get('system', 0):.1f}%")
        kv('Idle', f"{cpu.get('idle', 0):.1f}%")
        kv('IOWait', f"{cpu.get('iowait', 0):.1f}%")
    else:
        kv('CPU', '(esperando...)')

    section('Load Average')
    load = sistema.get('loadavg', {})
    if load:
        kv('1 min', f"{load.get('load_1min', 0):.2f}")
        kv('5 min', f"{load.get('load_5min', 0):.2f}")
        kv('15 min', f"{load.get('load_15min', 0):.2f}")
    else:
        kv('Load', '(esperando...)')

    section('Memoria del Sistema')
    mem = sistema.get('meminfo', {})
    if mem:
        total = mem.get('MemTotal', 0)
        free = mem.get('MemFree', 0)
        avail = mem.get('MemAvailable', 0)
        buffers = mem.get('Buffers', 0)
        cached = mem.get('Cached', 0)
        swap_total = mem.get('SwapTotal', 0)
        swap_free = mem.get('SwapFree', 0)
        kv('Total', f'{total} KB' if total else '?')
        kv('Libre', f'{free} KB' if free else '?')
        kv('Disponible', f'{avail} KB' if avail else '?')
        kv('Buffers', f'{buffers} KB' if buffers else '?')
        kv('Cached', f'{cached} KB' if cached else '?')
        if swap_total:
            kv('Swap Total', f'{swap_total} KB')
            kv('Swap Libre', f'{swap_free} KB')
    else:
        kv('Memoria', '(esperando...)')

    uptime_dict = sistema.get('uptime', {})
    uptime_val = uptime_dict.get('uptime') if isinstance(uptime_dict, dict) else None
    if uptime_val is not None:
        section('Uptime')
        kv('Uptime', f'{uptime_val:.0f} segundos ({uptime_val / 3600:.1f} horas)')

    stat_sys = sistema.get('stat_sys', {})
    btime = stat_sys.get('btime') if isinstance(stat_sys, dict) else None
    if btime:
        from datetime import datetime
        boot_dt = datetime.fromtimestamp(btime)
        kv('Boot Time', boot_dt.strftime('%Y-%m-%d %H:%M:%S'))

    section('Procesos')
    total = sistema.get('total_proc', 0)
    kv('Total', total)
    threads = sistema.get('threads_totales', 0)
    kv('Threads totales', threads)
    por_estado = sistema.get('por_estado', {})
    if por_estado:
        for estado, cant in sorted(por_estado.items()):
            kv(f'  Estado {estado}', cant)

    section('Top 3 CPU')
    top = sistema.get('top_cpu', [])
    if top:
        for i, t in enumerate(top, 1):
            nombre = t.get('name', '?')[:20]
            cpu_pct = t.get('cpu', 0)
            pid_t = t.get('pid', '?')
            kv(f'  {i}. {nombre}', f'PID {pid_t}  CPU: {cpu_pct:.1f}%')
    else:
        kv('Top CPU', '(esperando...)')

    section('Top 3 Memoria')
    top_m = sistema.get('top_mem', [])
    if top_m:
        for i, t in enumerate(top_m, 1):
            nombre = t.get('name', '?')[:20]
            rss = t.get('rss', 0)
            pid_t = t.get('pid', '?')
            kv(f'  {i}. {nombre}', f'PID {pid_t}  RSS: {rss:.0f} KB')
    else:
        kv('Top Memoria', '(esperando...)')

    return Panel(text, title='[bold]Sistema[/]', border_style='cyan')


def render_detalle(pid, resumen, memoria, fds, threads, senales, scheduling, verbose=False):
    r = resumen.get(pid, {}) if isinstance(resumen.get(pid), dict) else {}
    m = memoria.get(pid, {}) if isinstance(memoria.get(pid), dict) else {}
    fds_list = fds.get(pid, []) if isinstance(fds.get(pid), list) else []
    tids = threads.get(pid, []) if isinstance(threads.get(pid), list) else []
    s = senales.get(pid, {}) if isinstance(senales.get(pid), dict) else {}
    sc = scheduling.get(pid, {}) if isinstance(scheduling.get(pid), dict) else {}

    text = Text()

    def section(titulo):
        text.append(f'\n── {titulo} ', style='bold cyan')
        text.append('─' * 40, style='dim')
        text.append('\n')

    def kv(key, val, val_style=''):
        text.append(f'  {key}: ', style='bold')
        if val_style:
            text.append(str(val), style=val_style)
        else:
            text.append(str(val))
        text.append('\n')

    text.append(f'  PID: ', style='bold')
    text.append(str(pid), style='bold yellow')
    text.append('  |  ', style='dim')
    text.append(r.get('name', '?'), style='bold white')
    text.append('\n')

    section('Resumen')
    kv('Estado', r.get('state', '?'))
    kv('CPU%', f"{r.get('cpu_percent', 0.0):.1f}")
    kv('Usuario', r.get('user', r.get('uid', '?')))
    kv('UID', r.get('uid', '?'))
    kv('GID', f"{r.get('gid', '?')} ({r.get('group', '?')})")
    kv('PPID', r.get('ppid', '?'))
    kv('Threads', r.get('threads', 0))
    cmd = r.get('cmdline', [])
    if isinstance(cmd, list):
        cmd_str = ' '.join(str(x) for x in cmd)
    else:
        cmd_str = str(cmd)
    kv('Cmdline', cmd_str[:200] if cmd_str else '(none)')

    section('Memoria')
    kv('RSS (KB)', f"{m.get('rss', '?'):.0f}" if isinstance(m.get('rss'), (int, float)) else str(m.get('rss', '?')))
    kv('VSIZE (KB)', f"{m.get('vsize', '?'):.0f}" if isinstance(m.get('vsize'), (int, float)) else str(m.get('vsize', '?')))
    kv('VmData (KB)', f"{m.get('data', '?'):.0f}" if isinstance(m.get('data'), (int, float)) else str(m.get('data', '?')))
    kv('VmStk (KB)', f"{m.get('stack', '?'):.0f}" if isinstance(m.get('stack'), (int, float)) else str(m.get('stack', '?')))
    kv('VmExe (KB)', f"{m.get('exe', '?'):.0f}" if isinstance(m.get('exe'), (int, float)) else str(m.get('exe', '?')))
    kv('VmLib (KB)', f"{m.get('lib', '?'):.0f}" if isinstance(m.get('lib'), (int, float)) else str(m.get('lib', '?')))
    kv('Minor faults', m.get('faults_min', '?'))
    kv('Major faults', m.get('faults_maj', '?'))
    maps_val = m.get('maps')
    if isinstance(maps_val, list) and maps_val:
        grupos = {}
        for reg in maps_val:
            perms = reg.get('perms', '')
            path = reg.get('path', '')
            if path == '[heap]':
                tipo = 'heap'
            elif path == '[stack]':
                tipo = 'stack'
            elif not path:
                if 'x' in perms:
                    tipo = 'anon_exec'
                elif 'w' in perms:
                    tipo = 'anon_write'
                else:
                    tipo = 'anon_read'
            elif path.startswith('['):
                tipo = path.strip('[]')
            else:
                ext = path.rsplit('.', 1)[-1] if '.' in path else ''
                if ext in ('so', 'dll'):
                    tipo = 'shared_lib'
                else:
                    tipo = 'mapped_file'
            tam = (reg.get('fin', 0) - reg.get('inicio', 0)) // 1024
            if tipo not in grupos:
                grupos[tipo] = {'count': 0, 'kb': 0}
            grupos[tipo]['count'] += 1
            grupos[tipo]['kb'] += tam
        kv('Mapas totales', len(maps_val))
        for tipo in sorted(grupos):
            g = grupos[tipo]
            kv(f'  {tipo}', f'{g["count"]} regiones, {g["kb"]} KB')
    else:
        kv('Mapas memoria', 0)

    section('FDs')
    if fds_list:
        kv('Total abiertos', len(fds_list))
        fd_limit = 40 if verbose else 15
        for fd_info in fds_list[:fd_limit]:
            num = fd_info.get('fd', '?')
            dest = fd_info.get('destino', '?')
            kv(f'  FD {num}', dest[:50])
        if len(fds_list) > fd_limit:
            kv('  ...', f'y {len(fds_list) - fd_limit} más')
    else:
        kv('FDs', '(sin datos)')

    section('Threads')
    if tids:
        kv('Total', len(tids))
        thr_limit = 40 if verbose else 20
        for thr in tids[:thr_limit]:
            tid = thr.get('tid', '?')
            state = thr.get('state', '?')
            cpu = thr.get('cpu_percent', 0.0)
            kv(f'  TID {tid}', f'{state}  CPU: {cpu:.1f}%')
        if len(tids) > thr_limit:
            kv('  ...', f'y {len(tids) - thr_limit} más')
    else:
        kv('Threads', '(sin datos)')

    section('Señales')
    def lista_legible(val):
        if isinstance(val, list):
            return ', '.join(str(x) for x in val)
        return str(val) if val else '?'
    kv('SigBlk', lista_legible(s.get('SigBlk')))
    kv('SigIgn', lista_legible(s.get('SigIgn')))
    kv('SigCgt', lista_legible(s.get('SigCgt')))
    kv('SigPnd', lista_legible(s.get('SigPnd')))
    kv('ShdPnd', lista_legible(s.get('ShdPnd')))

    section('Scheduling')
    kv('Nice', sc.get('nice', '?'))
    kv('Priority', sc.get('priority', '?'))
    kv('Utime', sc.get('utime', '?'))
    kv('Stime', sc.get('stime', '?'))
    kv('RT Priority', sc.get('rt_priority', '?'))
    kv('Policy', sc.get('policy', '?'))
    kv('SID', sc.get('sessid', '?'))
    kv('PGID', sc.get('pgid', '?'))
    kv('Affinity', sc.get('affinity', '?'))
    kv('Vol ctx switches', sc.get('ctxt_vol', '?'))
    kv('Invol ctx switches', sc.get('ctxt_invol', '?'))

    return Panel(
        text,
        title=f'[bold]Detalle PID {pid}[/]',
        border_style='green',
    )


NOMBRES_ORDEN = {0: 'CPU', 1: 'RSS', 2: 'PID'}


def render_footer(filter_cmd='', sort_mode=0, intervalo=2.0, filter_mode=False,
                  filter_text='', filter_user_mode=False, filter_user_text='',
                  filter_uid='', verbose_mode=False):
    text = Text()

    if filter_mode:
        text.append('Filtrar: ', style='bold')
        text.append(filter_text + '_')
    elif filter_user_mode:
        text.append('Usuario: ', style='bold')
        text.append(filter_user_text + '_')
    else:
        text.append('1-7/rmftspg', style='bold')
        text.append('  \u2191\u2193')
        text.append('  /filtro')
        if filter_cmd:
            text.append(f'[{filter_cmd}]', style='yellow')
        text.append('  u:user')
        if filter_uid:
            text.append(f'[{filter_uid}]', style='yellow')
        text.append(f'  c:{NOMBRES_ORDEN.get(sort_mode, "?")}')
        text.append(f'  +/-:{intervalo:.1f}s')
        if verbose_mode:
            text.append('  V', style='bold yellow')
        text.append('  h  q')

    return Panel(text, style='bold white on blue')


def render_ayuda():
    text = Text()
    text.append('  TECLAS DEL MONITOR\n\n', style='bold cyan')
    text.append('  Navegación\n', style='bold')
    text.append('    \u2191 / \u2193    Mover selección\n')
    text.append('    Enter   Ver detalle del proceso\n')
    text.append('    q       Salir\n\n')
    text.append('  Vistas\n', style='bold')
    text.append('    1-7     Cambiar vista por número\n')
    text.append('    r m f   Resumen / Memoria / FDs\n')
    text.append('    t s p   Threads / Señales / Scheduling\n')
    text.append('    g       Sistema global\n\n')
    text.append('  Filtros y orden\n', style='bold')
    text.append('    /       Filtrar por nombre o comando\n')
    text.append('    u       Filtrar por usuario (nombre o UID)\n')
    text.append('    c       Cambiar orden (CPU/RSS/PID)\n\n')
    text.append('  Intervalos\n', style='bold')
    text.append('    +       Aumentar intervalo (+0.5s)\n')
    text.append('    -       Disminuir intervalo (-0.5s)\n\n')
    text.append('  Otros\n', style='bold')
    text.append('    h/?     Mostrar esta ayuda\n')
    text.append('    Enter   Cerrar vista / detalle / ayuda\n')
    text.append('    Esc     Cerrar vista / detalle / ayuda\n')

    return Panel(text, title='[bold]Ayuda[/]', border_style='cyan')
