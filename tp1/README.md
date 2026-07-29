# Monitor de Procesos y Threads

**Computación II — Universidad de Mendoza — 2026**

Monitor del sistema en tiempo real inspirado en `htop`, construido con `multiprocessing` en Python. Lee `/proc` directamente (sin `psutil`) y muestra la anatomía interna de cada proceso con 7 vistas alternables.

---

## Descripción general

El monitor lee el filesystem `/proc` del kernel Linux para extraer información detallada de cada proceso: estado, memoria, file descriptors, threads, señales, scheduling y estadísticas globales del sistema.

**Funcionalidades principales:**

- 7 vistas alternables: Resumen, Memoria, FDs, Threads, Señales, Scheduling, Sistema
- Navegación con teclado (flechas, Enter, `/`, `u`, `c`, `+/-`)
- 7 procesos analizadores en paralelo, cada uno con su propio intervalo de refresco
- Señales: SIGINT/SIGTERM (shutdown), SIGHUP (reload config), SIGUSR1 (dump JSON), SIGWINCH (repintar)
- Filtrado por usuario y por nombre de comando
- Ordenamiento por CPU%, RSS o PID

---

## Arquitectura

```
       ┌──────────────────────────────────────┐
       │           SNAPSHOT GLOBAL            │
       │      (Manager dict compartido)       │
       │  ┌─────────────────────────────────┐ │
       │  │ "resumen"   : {...}  ts: ...    │ │
       │  │ "memoria"   : {...}  ts: ...    │ │
       │  │ "fds"       : {...}  ts: ...    │ │
       │  │ "threads"   : {...}  ts: ...    │ │
       │  │ "senales"   : {...}  ts: ...    │ │
       │  │ "scheduling": {...}  ts: ...    │ │
       │  │ "sistema"   : {...}  ts: ...    │ │
       │  └─────────────────────────────────┘ │
       └────────▲─────────────────────▲───────┘
                │ escriben            │ lee
   ┌────────────┼─────────┬──────────┴────────┐
   │            │         │                    │
┌──▼──────┐ ┌───▼─────┐ ┌─▼──────┐  ...  ┌────▼─────┐
│Resumen  │ │Memoria  │ │FDs     │       │ Display  │
│cada 2s  │ │cada 3s  │ │cada 5s │       │ TUI      │
└─────────┘ └─────────┘ └────────┘       │ (vista   │
                                          │ activa)  │
   7 analizadores en paralelo,            └──────────┘
   cada uno con su propio ritmo
```

### Componentes

| Componente | Archivo | Responsabilidad |
|------------|---------|-----------------|
| **Entry point** | `src/main.py` | Inicializa Manager, lanza procesos, maneja loop principal con teclado y señales |
| **Recolector** | `src/recolector.py` | Lista PIDs desde `/proc` y los escribe al snapshot |
| **Resumen** | `src/analizadores/resumen.py` | Nombre, estado, PPID, UID, CPU%, threads, cmdline |
| **Memoria** | `src/analizadores/memoria.py` | RSS, VmSize, VmHWM, VmSwap, page faults, maps |
| **FDs** | `src/analizadores/fds.py` | File descriptors abiertos con tipo inferido (tty/socket/pipe/file) |
| **Threads** | `src/analizadores/threads.py` | LWPs, estado, CPU% por thread |
| **Señales** | `src/analizadores/senales.py` | SigBlk, SigIgn, SigCgt, SigPnd, ShdPnd decodificados |
| **Scheduling** | `src/analizadores/scheduling.py` | Nice, priority, policy, affinity, context switches |
| **Sistema** | `src/analizadores/sistema.py` | CPU global, loadavg, meminfo, Top 3 CPU/mem, procesos por estado |
| **Display** | `src/display.py` | 7 vistas TUI con Rich (Layout, Table, Panel, Text) |
| **Señales** | `src/senales.py` | Self-pipe pattern para manejo async-signal-safe |
| **Teclado** | `src/keyboard.py` | Raw mode + os.read() para input no bloqueante |
| **Procfs** | `src/procfs.py` | 13 funciones de parseo de `/proc` |

### Comunicación entre procesos

- **Snapshot global**: `Manager.dict()` compartido entre todos los procesos. Cada analizador escribe su sección (`snapshot['resumen']`, `snapshot['memoria']`, etc.) y el display lo lee directamente.
- **Intervalos**: `multiprocessing.Value('d')` por analizador. El display los modifica con `+`/`-` y los analizadores leen el valor en cada ciclo.
- **Shutdown**: `multiprocessing.Event()`. El loop principal lo setea y cada analizador lo consulta con `wait(timeout=intervalo)`.
- **Señales**: Self-pipe pattern — el handler escribe 1 byte al pipe, el loop principal lee con `select.select()` y despacha la acción correspondiente.

---

## Decisiones de diseño

### ¿Por qué `Manager.dict()` y no `Value`/`Array`?

El snapshot tiene estructura de diccionario anidado con datos de tipo variable (listas, dicts, strings, floats). `Value` y `Array` solo funcionan para tipos simples (int, float, bytes). `Manager.dict()` permite estructuras complejas y es serializado por un proceso server, lo que garantiza atomicidad a nivel de escritura de cada clave.

Para los intervalos, que son un solo float, usamos `multiprocessing.Value('d')` — más eficiente que pasar por Manager para un solo valor.

### ¿Por qué no Lock en el snapshot?

Las race conditions en este caso son benignas: si el display lee `snapshot['resumen']` mientras el analizador de memoria está escribiendo `snapshot['memoria']`, no hay conflicto porque cada proceso escribe una clave diferente. El peor caso es leer datos de un ciclo anterior, que es aceptable en un monitor de tiempo real. Un Lock serializaría innecesariamente 7 procesos.

### ¿Por qué self-pipe para señales?

Los handlers de señales en Python solo pueden ejecutar código async-signal-safe (pocas funciones de la stdlib). El patrón self-pipe permite: (1) el handler solo escribe 1 byte al pipe, (2) el loop principal detecta el byte con `select.select()` y ejecuta la lógica completa (relee config, hace dump, etc.) de forma segura.

### ¿Por qué `os.read()` en vez de `input()` para teclado?

`input()` lee línea completa (bloquea hasta Enter). Para una TUI que necesita responder a flechas y teclas individuales, usamos `os.read(fd, 1)` en raw mode, que lee bytes sin bloquear y permite detectar secuencias de escape de las flechas (`\x1bOA`, `\x1bOB`, etc.).

### ¿Por qué intervalos diferentes por vista?

Cada analizador tiene un costo diferente: Resumen lee archivos pequeños (~2s), FDs lista symlinks (~5s), Señales decodifica máscaras hexadecimales (~10s). Intervalos diferentes evitan sobrecargar el sistema con datos que no se están mostrando.

---

## Conceptos del curso aplicados

### Clase 3-4: Procesos, /proc, fork, exec, wait

- Todo el proyecto se basa en leer `/proc` para inspeccionar procesos desde fuera
- El PID y PPID se obtienen del nombre del directorio `/proc/<pid>/` y del campo `PPid` en `/proc/<pid>/status`
- Los zombies (estado Z) se detectan en la vista Sistema contando procesos por estado
- El `fork()` ocurre internamente al hacer `p = multiprocessing.Process(target=...)` y `p.start()` — el proceso hijo es el analizador, el padre sigue ejecutando el loop principal

### Clase 5: File descriptors, pipes

- `/proc/<pid>/fd/` muestra los file descriptors abiertos de cada proceso
- Los pipes anónimos se ven como `pipe:[inode]` en los symlinks
- El self-pipe pattern usa un pipe real (`os.pipe()`) para comunicación async-signal-safe
- `stdin`/`stdout`/`stderr` (FDs 0, 1, 2) se ven como `/dev/pts/N` o `/dev/null`

### Clase 6: Señales

- `signal.signal()` registra handlers para SIGINT, SIGTERM, SIGHUP, SIGUSR1, SIGUSR2
- El self-pipe es el patrón recomendado para manejar señales sin bloquear el loop principal
- Las señales se decodifican de máscaras hexadecimales (`SigBlk`, `SigIgn`, `SigCgt`) a nombres legibles
- `SIGWINCH` se captura para repintar al redimensionar la terminal

### Clase 7: mmap y memoria compartida

- `Manager.dict()` usa un proceso server con sockets internos para serializar datos entre procesos
- `multiprocessing.Value('d')` usa memoria compartida `mmap` internamente para un solo float

### Clase 8-9: Multiprocessing

- Cada analizador es un `multiprocessing.Process` con su propio `target` (loop infinito)
- `multiprocessing.Event()` coordina el shutdown entre procesos
- `fork` es el default en Linux: el hijo hereda el snapshot del padre, pero cada analizador escribe su propia clave
- El display corre en el proceso principal para tener acceso directo al terminal

### Clase 10: Threading, GIL

- El teclado usa `os.read()` en raw mode (no threads) para simplicidad
- El GIL no afecta porque usamos `multiprocessing`, no `multiprocessing.Thread`
- Cada thread en `/proc/<pid>/task/<tid>/` se analiza en la vista Threads

### Clase 11: Sincronización

- No usamos Lock porque las race conditions son benignas: cada analizador escribe una clave diferente del snapshot
- `Event.wait(timeout=)` es la primitiva de sincronización para shutdown
- Los `Value` para intervalos se modifican desde el display y se leen desde los analizadores — race condition benigna (el peor caso es un ciclo con el valor anterior)

---

## Limitaciones conocidas

1. **No persiste datos**: el monitor no guarda historial — al cerrar se pierden todos los datos
2. **Race conditions benignas**: no se garantiza consistencia instantánea entre vistas (puede haber hasta 1 ciclo de diferencia)
3. **Docker required**: solo funciona en Linux (resuelto con Docker en macOS)
4. **Sin autenticación**: no hay control de acceso — cualquier usuario puede ver todos los procesos
5. **FDs no sigue symlinks**: muestra el destino del symlink pero no resuelve archivos eliminados (deleted)
6. **Memoria compartida serializada**: `Manager.dict()` tiene overhead de serialización — no escala a miles de procesos sin degradación

---

## Cómo correr

### Requisitos

- Docker Desktop (macOS/Linux/Windows con WSL2)
- docker compose v2

### Ejecución

```bash
git clone <repo-url>
cd tp1
docker compose up --build
```

### Keybindings

| Tecla | Acción |
|-------|--------|
| `1`-`7` / `r/m/f/t/s/p/g` | Cambiar vista |
| `↑` `↓` | Navegar procesos |
| `Enter` | Pin proceso seleccionado |
| `/` | Filtrar por nombre |
| `u` | Filtrar por usuario (UID) |
| `c` | Ciclar orden (CPU% → RSS → PID) |
| `+` / `-` | Ajustar intervalo vista activa |
| `q` | Salir |
| `h` / `?` | Ayuda |

### Señales

```bash
# Recargar config (desde otro terminal)
docker compose exec monitor kill -HUP 1

# Dump snapshot a JSON
docker compose exec monitor kill -USR1 1

# Toggle verbose
docker compose exec monitor kill -USR2 1

# Shutdown limpio
docker compose exec monitor kill -SIGINT 1
```

### Archivos

- `config.json`: intervalos por vista (recolector, resumen, memoria, fds, threads, senales, scheduling, sistema)
- Los dumps se generan como `dump_<timestamp>.json` en el directorio actual

---
