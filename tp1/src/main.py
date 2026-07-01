import multiprocessing
import time

from recolector import recolector_loop
from agregador import agregador_loop


def main():
    with multiprocessing.Manager() as manager:
        snapshot = manager.dict()
        shutdown_event = multiprocessing.Event()

        intervalo_recolector = multiprocessing.Value('d', 2.0)
        intervalo_agregador = multiprocessing.Value('d', 2.0)

        recolector = multiprocessing.Process(
            target=recolector_loop,
            args=(snapshot, shutdown_event, intervalo_recolector),
        )
        agregador = multiprocessing.Process(
            target=agregador_loop,
            args=(snapshot, shutdown_event, intervalo_agregador),
        )

        recolector.start()
        agregador.start()

        try:
            while True:
                pids = snapshot.get('pids', [])
                datos = snapshot.get('datos', {})
                ts = snapshot.get('agregador_ts', 0)

                print("\033[2J\033[H", end='')
                print(f"Monitor - PIDs visibles: {len(pids)}")
                print(f"Última actualización: {ts:.1f}")
                print("-" * 80)
                print(f"{'PID':>7}  {'NOMBRE':<20} {'ESTADO':<5} {'CPU%':<6} {'RSS':<8} {'THR':<4}")
                print("-" * 80)

                for pid in sorted(datos.keys())[:15]:
                    d = datos[pid]
                    st = d.get('stat', {})
                    nombre = d.get('status', {}).get('Name', '?')
                    estado = st.get('state', '?')
                    utime = st.get('utime', 0)
                    stime = st.get('stime', 0)
                    threaded = st.get('num_threads', 0)
                    rss_pages = st.get('rss', 0)
                    rss_kb = rss_pages * 4

                    print(f"{pid:>7}  {str(nombre):<20} {estado:<5} {'?':<6} {rss_kb:<8} {threaded:<4}")

                if not datos:
                    print("(esperando datos del agregador...)")

                time.sleep(1)

        except KeyboardInterrupt:
            print("\nApagando...")
            shutdown_event.set()
            recolector.join(timeout=3)
            agregador.join(timeout=3)
            print("Terminado.")


if __name__ == '__main__':
    main()
