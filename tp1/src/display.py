from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


NOMBRES_VISTA = {
    1: 'Resumen', 2: 'Memoria', 3: 'FDs', 4: 'Threads',
    5: 'Señales', 6: 'Scheduling', 7: 'Sistema',
}


def crear_layout():
    layout = Layout()
    layout.split_column(
        Layout(name='header', size=3),
        Layout(name='main'),
        Layout(name='footer', size=3),
    )
    return layout


def render_header(pids_count, active_view, debug_tecla=''):
    nombre = NOMBRES_VISTA.get(active_view, '?')
    texto = f'Monitor - PIDs: {pids_count}  Vista: [{active_view}] {nombre}'
    if debug_tecla:
        texto += f'  Tecla: {debug_tecla}'
    return Panel(texto, style='bold cyan')


def render_vista_resumen(resumen, memoria, selected_idx, sort_mode,
                         filter_cmd, scroll_offset, max_rows, filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('EST', width=3)
    table.add_column('CPU%', justify='right', width=5)
    table.add_column('RSS', justify='right', width=8)
    table.add_column('THR', justify='right', width=3)
    table.add_column('PPID', justify='right', width=7)
    table.add_column('UID', justify='right', width=5)

    items = []
    for pid, d in resumen.items():
        if filter_uid and str(d.get('uid', '')) != filter_uid:
            continue
        nombre = str(d.get('name', '?'))[:16]
        estado = d.get('state', '?')[:3]
        cpu = d.get('cpu_percent', 0.0)
        thr = d.get('threads', 0)
        ppid = d.get('ppid', 0)
        uid = d.get('uid', '?')
        m = memoria.get(pid, {})
        rss = m.get('rss', '?')
        items.append((pid, nombre, estado, cpu, rss, thr, ppid, uid))

    if filter_cmd:
        items = [i for i in items if filter_cmd.lower() in i[1].lower()]

    if sort_mode == 0:
        items.sort(key=lambda x: x[3], reverse=True)
    elif sort_mode == 1:
        items.sort(key=lambda x: x[4] if isinstance(x[4], (int, float)) else 0, reverse=True)
    else:
        items.sort(key=lambda x: x[0])

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, estado, cpu, rss, thr, ppid, uid = items[i]
        style = 'reverse' if i == selected_idx else ''
        cpu_str = f'{cpu:.1f}'
        rss_str = f'{rss:.0f}' if isinstance(rss, (int, float)) else str(rss)
        table.add_row(str(pid), nombre, estado, cpu_str, rss_str,
                      str(thr), str(ppid), str(uid), style=style)

    return table, items


def render_vista_memoria(resumen, memoria, selected_idx, scroll_offset, max_rows,
                         filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('RSS(KB)', justify='right', width=9)
    table.add_column('VSIZE(KB)', justify='right', width=10)
    table.add_column('HWM(KB)', justify='right', width=8)
    table.add_column('SWAP(KB)', justify='right', width=8)
    table.add_column('MAPS', justify='right', width=5)

    items = []
    for pid, d in memoria.items():
        if filter_uid and str(resumen.get(pid, {}).get('uid', '')) != filter_uid:
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        rss = d.get('rss', 0)
        vsize = d.get('vsize', 0)
        hwm = d.get('hwm', 0)
        swap = d.get('swap', 0)
        maps_val = d.get('maps')
        maps_count = len(maps_val) if isinstance(maps_val, list) else 0
        items.append((pid, nombre, rss, vsize, hwm, swap, maps_count))

    items.sort(key=lambda x: x[2] if isinstance(x[2], (int, float)) else 0, reverse=True)

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, rss, vsize, hwm, swap, maps_count = items[i]
        style = 'reverse' if i == selected_idx else ''
        rss_str = f'{rss:.0f}' if isinstance(rss, (int, float)) else str(rss)
        vsize_str = f'{vsize:.0f}' if isinstance(vsize, (int, float)) else str(vsize)
        hwm_str = f'{hwm:.0f}' if isinstance(hwm, (int, float)) else str(hwm)
        swap_str = f'{swap:.0f}' if isinstance(swap, (int, float)) else str(swap)
        table.add_row(str(pid), nombre, rss_str, vsize_str, hwm_str, swap_str,
                      str(maps_count), style=style)

    return table, items


def render_vista_fds(resumen, fds, selected_idx, scroll_offset, max_rows,
                     filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('FDS', justify='right', width=4)
    table.add_column('TIPOS', width=30)

    items = []
    for pid, fds_list in fds.items():
        if not isinstance(fds_list, list):
            continue
        if filter_uid and str(resumen.get(pid, {}).get('uid', '')) != filter_uid:
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
                         filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=20)
    table.add_column('THR', justify='right', width=5)
    table.add_column('DETALLE', width=40)

    items = []
    for pid, tids in threads.items():
        if not isinstance(tids, list):
            continue
        if filter_uid and str(resumen.get(pid, {}).get('uid', '')) != filter_uid:
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:20]
        estados = {}
        for t in tids:
            s = t.get('state', '?')
            estados[s] = estados.get(s, 0) + 1
        detalle = ' '.join(f'{s}:{c}' for s, c in sorted(estados.items()))
        items.append((pid, nombre, len(tids), detalle))

    items.sort(key=lambda x: x[2], reverse=True)

    if not items:
        table.add_row('(sin datos)', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, count, detalle = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, str(count), detalle[:40], style=style)

    return table, items


def render_vista_senales(resumen, senales, selected_idx, scroll_offset, max_rows,
                         filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('Blk', width=12)
    table.add_column('Ign', width=12)
    table.add_column('Cgt', width=12)
    table.add_column('Pnd', width=12)

    items = []
    for pid, d in senales.items():
        if not isinstance(d, dict):
            continue
        if filter_uid and str(resumen.get(pid, {}).get('uid', '')) != filter_uid:
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        blk = ','.join(d.get('SigBlk', []))[:12]
        ign = ','.join(d.get('SigIgn', []))[:12]
        cgt = ','.join(d.get('SigCgt', []))[:12]
        pnd = ','.join(d.get('SigPnd', []))[:12]
        items.append((pid, nombre, blk, ign, cgt, pnd))

    items.sort(key=lambda x: x[0])

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, blk, ign, cgt, pnd = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, blk, ign, cgt, pnd, style=style)

    return table, items


def render_vista_scheduling(resumen, scheduling, selected_idx, scroll_offset, max_rows,
                            filter_uid=''):
    table = Table(show_header=True, header_style='bold magenta')
    table.add_column('PID', justify='right', width=7)
    table.add_column('NOMBRE', width=16)
    table.add_column('NI', justify='right', width=4)
    table.add_column('PRI', justify='right', width=4)
    table.add_column('POLICY', width=6)
    table.add_column('AFFINITY', width=8)
    table.add_column('CTX-V', justify='right', width=6)
    table.add_column('CTX-I', justify='right', width=6)

    items = []
    for pid, d in scheduling.items():
        if not isinstance(d, dict):
            continue
        if filter_uid and str(resumen.get(pid, {}).get('uid', '')) != filter_uid:
            continue
        nombre = str(resumen.get(pid, {}).get('name', '?'))[:16]
        nice = d.get('nice', '?')
        pri = d.get('priority', '?')
        policy = str(d.get('policy', '?'))[:6]
        affinity = str(d.get('affinity', '?'))[:8]
        nvcsw = d.get('nvcsw', '?')
        nivcsw = d.get('nivcsw', '?')
        items.append((pid, nombre, nice, pri, policy, affinity, nvcsw, nivcsw))

    items.sort(key=lambda x: x[0])

    if not items:
        table.add_row('(sin datos)', '', '', '', '', '', '', '')
        return table, items

    if max_rows < 1:
        max_rows = 1

    end = min(scroll_offset + max_rows, len(items))
    for i in range(scroll_offset, end):
        pid, nombre, nice, pri, policy, affinity, nvcsw, nivcsw = items[i]
        style = 'reverse' if i == selected_idx else ''
        table.add_row(str(pid), nombre, str(nice), str(pri), policy, affinity,
                      str(nvcsw), str(nivcsw), style=style)

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
        kv('Total', f'{total} KB' if total else '?')
        kv('Libre', f'{free} KB' if free else '?')
        kv('Disponible', f'{avail} KB' if avail else '?')
    else:
        kv('Memoria', '(esperando...)')

    uptime_dict = sistema.get('uptime', {})
    uptime_val = uptime_dict.get('uptime') if isinstance(uptime_dict, dict) else None
    if uptime_val is not None:
        section('Uptime')
        kv('Uptime', f'{uptime_val:.0f} segundos ({uptime_val / 3600:.1f} horas)')

    section('Procesos')
    total = sistema.get('total_proc', 0)
    kv('Total', total)
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


def render_detalle(pid, resumen, memoria, fds, threads, senales, scheduling):
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
    kv('Threads', r.get('threads', 0))
    cmd = r.get('cmdline', '')
    kv('Cmdline', cmd[:80] if cmd else '(none)')

    section('Memoria')
    kv('RSS (KB)', f"{m.get('rss', '?'):.0f}" if isinstance(m.get('rss'), (int, float)) else str(m.get('rss', '?')))
    kv('VSIZE (KB)', f"{m.get('vsize', '?'):.0f}" if isinstance(m.get('vsize'), (int, float)) else str(m.get('vsize', '?')))
    kv('Minor faults', m.get('minflt', '?'))
    kv('Major faults', m.get('majflt', '?'))
    maps_val = m.get('maps')
    kv('Mapas memoria', len(maps_val) if isinstance(maps_val, list) else 0)

    section('FDs')
    if fds_list:
        kv('Total abiertos', len(fds_list))
        for fd_info in fds_list[:15]:
            num = fd_info.get('fd', '?')
            dest = fd_info.get('destino', '?')
            kv(f'  FD {num}', dest[:50])
        if len(fds_list) > 15:
            kv('  ...', f'y {len(fds_list) - 15} más')
    else:
        kv('FDs', '(sin datos)')

    section('Threads')
    if tids:
        kv('Total', len(tids))
        for thr in tids[:20]:
            tid = thr.get('tid', '?')
            state = thr.get('state', '?')
            cpu = thr.get('cpu_percent', 0.0)
            kv(f'  TID {tid}', f'{state}  CPU: {cpu:.1f}%')
        if len(tids) > 20:
            kv('  ...', f'y {len(tids) - 20} más')
    else:
        kv('Threads', '(sin datos)')

    section('Señales')
    kv('SigBlk', s.get('SigBlk', '?'))
    kv('SigIgn', s.get('SigIgn', '?'))
    kv('SigCgt', s.get('SigCgt', '?'))
    kv('SigPnd', s.get('SigPnd', '?'))
    kv('ShdPnd', s.get('ShdPnd', '?'))

    section('Scheduling')
    kv('Nice', sc.get('nice', '?'))
    kv('Priority', sc.get('priority', '?'))
    kv('Policy', sc.get('policy', '?'))
    kv('Affinity', sc.get('affinity', '?'))
    kv('Vol ctx switches', sc.get('nvcsw', '?'))
    kv('Invol ctx switches', sc.get('nivcsw', '?'))

    return Panel(
        text,
        title=f'[bold]Detalle PID {pid}[/]',
        border_style='green',
    )


NOMBRES_ORDEN = {0: 'CPU', 1: 'RSS', 2: 'PID'}


def render_footer(filter_cmd='', sort_mode=0, intervalo=2.0, filter_mode=False,
                  filter_text='', filter_user_mode=False, filter_user_text='',
                  filter_uid=''):
    text = Text()

    if filter_mode:
        text.append('Filtrar: ', style='bold')
        text.append(filter_text + '_')
    elif filter_user_mode:
        text.append('UID: ', style='bold')
        text.append(filter_user_text + '_')
    else:
        text.append('1-7/rmftspg', style='bold')
        text.append('  \u2191\u2193')
        text.append('  /filtro')
        if filter_cmd:
            text.append(f'[{filter_cmd}]', style='yellow')
        text.append('  u:uid')
        if filter_uid:
            text.append(f'[{filter_uid}]', style='yellow')
        text.append(f'  c:{NOMBRES_ORDEN.get(sort_mode, "?")}')
        text.append(f'  +/-:{intervalo:.1f}s')
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
    text.append('    /       Filtrar por nombre de proceso\n')
    text.append('    u       Filtrar por UID (número)\n')
    text.append('    c       Cambiar orden (CPU/RSS/PID)\n\n')
    text.append('  Intervalos\n', style='bold')
    text.append('    +       Aumentar intervalo (+0.5s)\n')
    text.append('    -       Disminuir intervalo (-0.5s)\n\n')
    text.append('  Otros\n', style='bold')
    text.append('    h/?     Mostrar esta ayuda\n')
    text.append('    Enter   Cerrar vista / detalle / ayuda\n')
    text.append('    Esc     Cerrar vista / detalle / ayuda\n')

    return Panel(text, title='[bold]Ayuda[/]', border_style='cyan')
