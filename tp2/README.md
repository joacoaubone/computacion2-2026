# TP2 - Plataforma de Tareas Distribuidas

API HTTP del Trabajo Práctico Nº 2 de Computación II. El sistema acepta tareas
asíncronas de descarga, hash y espera, y permite consultar su estado y resultado.

## Arquitectura

```text
+----------+      +----------------------+      +-------------------+
| Cliente  | ---> | FastAPI               | ---> | TaskRegistry      |
+----------+      | POST/GET/DELETE tareas|      | estado/resultados|
                  +----------+-----------+      +---------+---------+
                             | encola ID                   ^
                             v                             |
                  +----------+-----------+                |
                  | asyncio.Queue        |                |
                  +----------+-----------+                |
                             | consume ID                 |
                             v                             |
                  +----------+-----------+                |
                  | WorkerPool (N workers)|----------------+
                  +---+----------+--------+
                      |          |
          +-----------+          +----------------+
          |                                        |
          v                                        v
+---------+-----------+                 +----------+----------+
| descargar           |                 | esperar / hashear   |
| httpx.AsyncClient   |                 | asyncio / executor  |
+---------------------+                 +---------------------+
```

`POST /tareas` valida el tipo, guarda la tarea como `pendiente` y encola su ID.
Un worker la pasa a `ejecutando`, ejecuta el handler correspondiente y registra
resultado, error o cancelación. Los endpoints de consulta leen el mismo registro.

## Ejecutar localmente

Desde este directorio, con Python 3.11 o superior:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

La API queda disponible en `http://localhost:8000`. La documentación interactiva
de FastAPI está en `http://localhost:8000/docs`. El pool de workers se configura
con `TP2_WORKERS` (default `4`) y el executor con `TP2_PROCESS_POOL_WORKERS`
(default `2`). Cada tarea tiene un timeout configurable por
`TP2_TASK_TIMEOUT_SECONDS` (default `60`). El máximo de registros retenidos se
configura con `TP2_MAX_RETAINED_TASKS` (default `1000`). Los snapshots se guardan
bajo `TP2_STATE_DIR` (default `./data`).

## Ejecutar con Docker Compose

Desde este directorio:

```bash
docker compose up --build
```

La API queda publicada en `http://localhost:8000`:

```bash
curl http://localhost:8000/estadisticas
```

El servicio monta `./data` del host para conservar los snapshots. Para detenerlo
ordenadamente, usá `Ctrl+C` en la terminal de Compose o, desde otra terminal:

```bash
docker compose stop
```

`docker compose stop` envía SIGTERM al contenedor. También podés usar
`docker compose down`; el directorio enlazado `./data` permanece en el host.

## Enviar tareas

`POST /tareas` responde `202 Accepted` al aceptar una tarea, sin esperar su
ejecución. El campo `tipo` discrimina los formatos; los campos específicos van
directamente en el objeto JSON:

```bash
# Esperar dos segundos
curl -i -X POST http://localhost:8000/tareas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"esperar","segundos":2}'

# Calcular SHA-256 iterado
curl -i -X POST http://localhost:8000/tareas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"hashear","texto":"hola","iteraciones":1000}'

# Descargar varias URLs
curl -i -X POST http://localhost:8000/tareas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"descargar","urls":["https://example.com"]}'
```

`iteraciones` debe ser mayor que cero; `segundos` debe ser cero o mayor; y
`urls` debe contener al menos una URL HTTP o HTTPS. Un `tipo` desconocido, un
campo requerido ausente o un campo adicional no admitido responde `422` y no
encola la solicitud.

Una respuesta aceptada tiene esta forma:

```json
{
  "id": "<identificador-opaco>",
  "tipo": "esperar",
  "estado": "pendiente",
  "creado_en": "<fecha-hora ISO 8601>",
  "iniciado_en": null,
  "terminado_en": null,
  "duracion_segundos": null,
  "resultado": null,
  "error": null
}
```

Cuando termina, `resultado` contiene el resultado según el tipo de tarea:

- `esperar`: `{"segundos": 2.0}`.
- `hashear`: digest SHA-256 iterado codificado en hexadecimal.
- `descargar`: lista con `url`, `status_code`, `size_bytes` y `elapsed_seconds`
  por URL; una solicitud fallida incluye además `error` y no descarta los
  resultados de las demás URLs.

## Consultar tareas

```bash
# Listar todas o filtrar por estado
curl 'http://localhost:8000/tareas'
curl 'http://localhost:8000/tareas?estado=pendiente'

# Consultar una tarea por ID
curl 'http://localhost:8000/tareas/<id>'
```

Los estados posibles son `pendiente`, `ejecutando`, `completada`, `fallida` y
`cancelada`. El detalle incluye resultado o motivo de error cuando están
disponibles. Un ID inexistente responde `404`; un filtro de estado no válido
responde `422`.

| Endpoint | Respuesta esperada | Errores principales |
|---|---|---|
| `POST /tareas` | `202`, ID y estado `pendiente` | `422` si el tipo o sus campos no son válidos; `429` por saturación; `503` durante el apagado |
| `GET /tareas` | `200`, lista (opcionalmente filtrada por `estado`) | `422` si el filtro no es un estado válido |
| `GET /tareas/{id}` | `200`, estado y resultado/error disponible | `404` si el ID no existe |
| `DELETE /tareas/{id}` | `200` después de cancelar y completar la limpieza | `404` si el ID no existe; `409` si ya es terminal |
| `GET /estadisticas` | `200`, totales por estado, promedio de duración y workers ocupados | — |

## Cancelar tareas

```bash
curl -i -X DELETE 'http://localhost:8000/tareas/<id>'
```

- `200`: la tarea fue cancelada. Para una tarea en ejecución, la respuesta se
  envía luego de completar la limpieza.
- `404`: no existe una tarea con ese ID.
- `409`: la tarea ya está en un estado terminal y no se modifica; la respuesta
  informa el estado actual.

## Estadísticas

```bash
curl 'http://localhost:8000/estadisticas'
```

La respuesta contiene totales en `por_estado`, el promedio de duración en
`duracion_promedio_segundos` (o `null` si todavía no hay duraciones registradas)
y el total actual de `workers_ocupados`.

## Límite de tareas y retención

El servicio conserva como máximo `TP2_MAX_RETAINED_TASKS` registros (default
`1000`), contando tareas pendientes, en ejecución y terminales. La cola también
tiene ese límite. Si se llena la cola o todos los registros disponibles siguen
pendientes/en ejecución, `POST /tareas` responde `429 Too Many Requests` sin
crear ni encolar la nueva tarea; el cliente puede reintentar más tarde.

Cuando el registro llegó a su capacidad pero hay historial terminal, la próxima
admisión elimina los registros terminales más antiguos hasta liberar espacio.
Las tareas pendientes o en ejecución nunca se purgan. Por eso un ID antiguo
puede dejar de existir y responder `404`; `/tareas`, `/estadisticas` y el próximo
snapshot representan solo los registros que todavía se retienen.

## Apagado y snapshots

Al recibir SIGTERM o SIGINT, la API deja de aceptar tareas y drena las tareas ya
aceptadas durante el período configurado por `TP2_SHUTDOWN_TIMEOUT_SECONDS`
(default `10` segundos). Si vence el plazo, cancela la ejecución activa y guarda
las tareas aún no iniciadas como `pendiente`. El snapshot atómico
`estado_<timestamp>.json` queda en `TP2_STATE_DIR` (`./data` local;
`/app/data` dentro del contenedor y montado como `./data` en el host).

Al iniciar, el servicio informa por log el snapshot más reciente, pero **no
restaura ni vuelve a ejecutar** esas tareas.

## Limitaciones conocidas y reflexión personal

- El registro operativo es en memoria; el JSON es una copia para inspección, no
  un mecanismo de recuperación o reanudación.
- El registro y la cola están acotados por `TP2_MAX_RETAINED_TASKS`; al saturarse,
  nuevas altas reciben `429`, y resultados terminales antiguos pueden purgarse.
- Si se agota el plazo de apagado, las tareas activas se cancelan y las que no
  llegaron a empezar quedan pendientes en el snapshot.
- La cancelación de `hashear` es cooperativa: espera a que termine el lote de
  SHA-256 que ya se está ejecutando en el proceso hijo.
- El servicio no incluye autenticación, broker distribuido ni coordinación
  entre varias instancias.

**Completar personalmente antes de entregar (2–3 párrafos):**

- ¿Qué aprendiste sobre el drenaje de una cola y el cierre de recursos al apagar?
- ¿Qué diferencia observaste entre detener un worker y guardar el estado para
  inspeccionarlo después?
- ¿Qué limitación o decisión de diseño cambiarías si el servicio tuviera que
  reanudar tareas automáticamente?

## Decisiones de diseño y conceptos del curso

- **Productor-consumidor y event loop (clases 17–18):** `POST /tareas` produce
  IDs en una `asyncio.Queue`; las corrutinas worker los consumen. Las
  transiciones del registro son operaciones síncronas breves dentro del mismo
  event loop, por lo que no intercalan ejecución ni requieren `Lock`.
- **I/O asíncrono y multiplexing (clases 13–14, 17 y 20–21):** cada descarga
  usa `httpx.AsyncClient`; las URLs se esperan concurrentemente dentro de un
  `asyncio.TaskGroup`, permitiendo que el event loop atienda otras corrutinas
  mientras espera la red y espere la limpieza de los requests si se cancela el
  grupo.
- **CPU-bound y `concurrent.futures` (clase 22):** hashear no se delega a una
  corrutina por sí sola, porque el cálculo Python bloquearía el event loop. Se
  ejecuta por lotes en `ProcessPoolExecutor`; la coroutine espera cada lote y
  puede atender HTTP entre lotes.
- **Cancelación (clases 18 y 20–21):** `esperar` usa `asyncio.sleep`, no
  `time.sleep`; el `DELETE` cancela la ejecución y espera a que el worker marque
  la tarea `cancelada` tras completar la limpieza. Los errores de una tarea se
  guardan como `fallida` sin matar el worker. Cada request de descarga usa un
  context manager HTTP para liberar la respuesta también ante cancelación.
- **Aislamiento de excepciones:** un error esperado de una URL se devuelve junto
  a esa URL y no descarta los resultados de sus hermanas; una excepción de
  handler marca esa tarea `fallida`, y el consumidor continúa con la siguiente.
- **Starlette y ASGI:** FastAPI se apoya en Starlette para el ciclo ASGI y el
  enrutamiento. El proyecto define rutas y validación mediante FastAPI.

## Mediciones

Las mediciones se pueden repetir desde la raíz del repositorio:

```bash
python -m tp2.benchmarks.measurements
```

El script inicia un servidor de benchmark temporal en `127.0.0.1`, ejecuta las
tres pruebas y emite el entorno y los resultados en JSON. Las rutas
`/__benchmark/*` solo existen en ese servidor local; no forman parte de la API
normal. Los snapshots de ese proceso se escriben bajo `tp2/data/`, que está
ignorado por Git junto con los datos de ejecución normales.

**Entorno de esta ejecución:** Python 3.13.5, macOS 26.5.1 arm64, 4 workers de
coroutines (`TP2_WORKERS`) y 2 procesos (`TP2_PROCESS_POOL_WORKERS`). Los valores
son una muestra de esta máquina; pueden variar entre ejecuciones y plataformas.
El JSON completo de esta ejecución está en
[`benchmarks/validation-results.json`](benchmarks/validation-results.json).

### Concurrencia I/O: 20 descargas

Las 20 solicitudes HTTP apuntaron al servidor local de benchmark, que agrega
20 ms de espera asíncrona por respuesta. Así se compara la concurrencia del
cliente sin depender de la disponibilidad o rate limits de sitios externos.

| Ejecución | Tiempo |
|---|---:|
| Secuencial | 0,4877 s |
| Concurrente | 0,0524 s |
| Speedup | **9,31×** |

Las solicitudes se solapan: el tiempo concurrente se acerca al de una sola
espera más el costo de red local, no a la suma de las 20 esperas.

### Event loop durante CPU-bound

El endpoint aislado de benchmark aplica 750.000 hashes SHA-256 en línea
(bloqueando deliberadamente el event loop) o vía `ProcessPoolExecutor`. Se mide
el tiempo de `GET /tareas` 50 ms después de iniciar el hash.

| Modo de hash | Latencia de `GET /tareas` | Tiempo de la solicitud de hash |
|---|---:|---:|
| Inline, sin executor | 111,2 ms | 148,5 ms |
| `ProcessPoolExecutor` | 8,5 ms | 253,2 ms |

El executor mantiene disponible el event loop para responder HTTP mientras el
cálculo sigue en otro proceso. La mayor duración total del hash con executor
incluye el costo de iniciar/coordinar el proceso; la comparación relevante aquí
es la latencia concurrente de la API.

### Techo del pool

Se enviaron lotes crecientes de tareas `hashear`, de 500.000 iteraciones cada
una. Cada punto es la mediana de tres ejecuciones, con cuatro workers de
coroutines y un `ProcessPoolExecutor` de dos procesos.

| Tareas en el lote | Tiempo mediano | Throughput |
|---:|---:|---:|
| 1 | 0,1127 s | 8,87 tareas/s |
| 2 | 0,1385 s | 14,44 tareas/s |
| 4 | 0,2439 s | 16,40 tareas/s |
| 8 | 0,4975 s | 16,08 tareas/s |
| 16 | 0,9706 s | 16,48 tareas/s |

En esta ejecución el throughput se estabiliza entre **16,1 y 16,5 tareas/s**
desde los lotes de cuatro; al duplicar de 8 a 16 tareas, el tiempo total casi se
duplica sin un aumento material del throughput. En esta carga el cálculo
CPU-bound y los dos procesos del executor son el techo, no la cantidad de
corrutinas HTTP. El encolado adicional agrega latencia, pero no capacidad de CPU.
