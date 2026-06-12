import os


def listar_procesos(limite=10):
    pids = sorted(
        [int(d) for d in os.listdir('/proc') if d.isdigit()],
    )[:limite]
    for pid in pids:
        try:
            with open(f'/proc/{pid}/status') as f:
                for line in f:
                    if line.startswith('Name:'):
                        nombre = line.split()[1]
                        break
            print(f"PID {pid:>6}  {nombre}")
        except (FileNotFoundError, PermissionError):
            print(f"PID {pid:>6}  (sin acceso)")


if __name__ == '__main__':
    print(f"Linux version: {os.uname().release}")
    total = len([d for d in os.listdir('/proc') if d.isdigit()])
    print(f"Procesos visibles: {total}")
    print("\nPrimeros 10 procesos:")
    listar_procesos()
