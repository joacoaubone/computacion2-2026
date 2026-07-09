import multiprocessing
import time

from recolector import recolector_loop
from analizadores.resumen import resumen_loop
from analizadores.memoria import memoria_loop
from analizadores.sistema import sistema_loop


def main():
    with multiprocessing.Manager() as manager:
        snapshot = manager.dict()
        shutdown_event = multiprocessing.Event()

        intervalos = {
            'recolector': multiprocessing.Value('d', 2.0),
            'resumen': multiprocessing.Value('d', 2.0),
            'memoria': multiprocessing.Value('d', 3.0),
            'sistema': multiprocessing.Value('d', 2.0),
        }

        procesos = [
            multiprocessing.Process(
                target=recolector_loop,
                args=(snapshot, shutdown_event, intervalos['recolector']),
            ),
            multiprocessing.Process(
                target=resumen_loop,
                args=(snapshot, shutdown_event, intervalos['resumen']),
            ),
            multiprocessing.Process(
                target=memoria_loop,
                args=(snapshot, shutdown_event, intervalos['memoria']),
            ),
            multiprocessing.Process(
                target=sistema_loop,
                args=(snapshot, shutdown_event, intervalos['sistema']),
            ),
        ]

        for p in procesos:
            p.start()

        try:
            while True:
                import os
                os.system('TERM=xterm clear')

                resumen = snapshot.get('resumen', {})
                memoria = snapshot.get('memoria', {})
                sistema = snapshot.get('sistema', {})
                pids = snapshot.get('pids', [])

                print(f"Monitor - PIDs: {len(pids)}")
                print(f"Resumen: {snapshot.get('resumen_ts', 0):.1f}s  "
                      f"Memoria: {snapshot.get('memoria_ts', 0):.1f}s  "
                      f"Sistema: {snapshot.get('sistema_ts', 0):.1f}s")
                print("-" * 90)
                print(f"{'PID':>7}  {'NOMBRE':<20} {'ESTADO':<5} {'CPU%':<7} {'RSS(KB)':<9} {'THR':<4}")
                print("-" * 90)

                for pid in sorted(resumen.keys())[:15]:
                    d = resumen[pid]
                    nombre = d.get('name', '?')[:20]
                    estado = d.get('state', '?')
                    cpu = d.get('cpu_percent', 0.0)
                    thr = d.get('threads', 0)
                    m = memoria.get(pid, {})
                    rss = m.get('rss', '?')
                    if isinstance(rss, (int, float)):
                        rss = f"{rss:.0f}"
                    print(f"{pid:>7}  {nombre:<20} {estado:<5} {cpu:<7} {str(rss):<9} {thr:<4}")

                if not resumen:
                    print("(esperando datos del resumen...)")
                    time.sleep(1)
                    continue

                sys = sistema
                cpu_data = sys.get('cpu', {})
                if cpu_data:
                    print(f"\nCPU: user={cpu_data.get('user', 0)}%  "
                          f"system={cpu_data.get('system', 0)}%  "
                          f"idle={cpu_data.get('idle', 0)}%  "
                          f"iowait={cpu_data.get('iowait', 0)}%")

                load = sys.get('loadavg')
                if load:
                    print(f"Load: {load.get('load_1min', 0):.2f}  "
                          f"{load.get('load_5min', 0):.2f}  "
                          f"{load.get('load_15min', 0):.2f}")

                top = sys.get('top_cpu', [])
                if top:
                    top_str = '  '.join(f"{t['name'][:10]}({t['cpu']:.1f}%)" for t in top)
                    print(f"Top CPU: {top_str}")

                time.sleep(1)

        except KeyboardInterrupt:
            print("\nApagando...")
            shutdown_event.set()
            for p in procesos:
                p.join(timeout=3)
            print("Terminado.")


if __name__ == '__main__':
    main()
