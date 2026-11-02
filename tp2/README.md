# TP2 — Plataforma de Tareas Distribuidas

Trabajo Práctico Nº 2 de Computación II — Universidad de Mendoza — 2026.

## 1. Descripción y uso

La plataforma recibe tareas por HTTP, las encola para su ejecución concurrente y permite consultar su estado y resultado. Soporta tres tipos: `descargar` (I/O de red), `hashear` (cálculo CPU-bound) y `esperar` (espera asíncrona). El `POST /tareas` devuelve `202 Accepted` después de aceptar y encolar la tarea; no espera a que termine.

### Ejecutar con Docker Compose

Desde el directorio `tp2/`, donde están el `Dockerfile` y `docker-compose.yml`:

```bash
docker compose up --build
```

La API queda disponible en `http://localhost:8000` y la documentación interactiva de FastAPI en `http://localhost:8000/docs`. Para detener el servicio ordenadamente, presioná `Ctrl+C` o ejecutá desde otra terminal:

```bash
docker compose stop
```

También podés usar `docker compose down`. Los snapshots quedan en `tp2/data/` del host gracias al volumen configurado en Compose.

### Ejecutar localmente

Desde el directorio `tp2/`, con Python 3.11 o superior:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

La configuración se puede modificar con variables de entorno: `TP2_WORKERS` (default `4`), `TP2_PROCESS_POOL_WORKERS` (`2`), `TP2_TASK_TIMEOUT_SECONDS` (`60`), `TP2_SHUTDOWN_TIMEOUT_SECONDS` (`10`), `TP2_MAX_RETAINED_TASKS` (`1000`) y `TP2_STATE_DIR` (`./data`).

### Enviar tareas con `curl`

Esperar dos segundos:

```bash
curl -i -X POST http://localhost:8000/tareas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"esperar","segundos":2}'
```

Calcular un hash SHA-256 iterado:

```bash
curl -i -X POST http://localhost:8000/tareas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"hashear","texto":"hola","iteraciones":1000}'
```

Descargar una o más URLs:

```bash
curl -i -X POST http://localhost:8000/tareas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"descargar","urls":["https://example.com"]}'
```

La respuesta aceptada incluye un `id` y normalmente el estado inicial `pendiente`. Usá ese ID para consultar o cancelar la tarea:

```bash
curl 'http://localhost:8000/tareas/<id>'
curl 'http://localhost:8000/tareas'
curl 'http://localhost:8000/tareas?estado=pendiente'
curl -i -X DELETE 'http://localhost:8000/tareas/<id>'
curl 'http://localhost:8000/estadisticas'
```

Los estados posibles son `pendiente`, `ejecutando`, `completada`, `fallida` y `cancelada`. Una tarea `descargar` devuelve por URL el código HTTP, el tamaño y el tiempo; los errores individuales se incluyen en el resultado sin descartar las demás descargas. `hashear` devuelve el digest hexadecimal y `esperar`, la cantidad de segundos solicitada.

Pydantic valida los cuerpos: `iteraciones` debe ser mayor que cero, `segundos` no puede ser negativo y `urls` debe contener al menos una URL HTTP o HTTPS. Un tipo desconocido, un campo requerido ausente o un campo adicional no permitido responde `422`.

| Endpoint | Respuesta esperada | Errores principales |
|---|---|---|
| `POST /tareas` | `202`, ID y estado inicial | `422` por datos inválidos; `429` por saturación; `503` durante el apagado |
| `GET /tareas` | `200`, lista filtrable por estado | `422` si el filtro no es válido |
| `GET /tareas/{id}` | `200`, estado y resultado/error | `404` si el ID no existe |
| `DELETE /tareas/{id}` | `200` si se cancela | `404` si no existe; `409` si ya terminó o no se pudo cancelar |
| `GET /estadisticas` | `200`, totales, duración promedio y workers ocupados | — |

La plataforma conserva hasta `TP2_MAX_RETAINED_TASKS` registros. Si se llena la cola o no quedan registros terminales que puedan purgarse, las nuevas solicitudes reciben `429`. Los registros terminales más antiguos pueden eliminarse para liberar lugar; los pendientes y en ejecución no se purgan.

### Pruebas automatizadas

Desde la raíz del repositorio:

```bash
python -m pytest tp2/tests -v
```

## 2. Diagrama de arquitectura

```text
Cliente HTTP
    |
    v
FastAPI — api.py
    | POST: valida, crea registro y encola el ID
    +-----------------------> TaskRegistry — tasks.py
    |                              estado y resultados
    v
asyncio.Queue
    |
    v
WorkerPool — workers.py (N corrutinas)
    |
    v
TaskExecutor — execution.py
    +--> descargar: handlers.py -> httpx.AsyncClient -> URLs concurrentes
    +--> esperar: asyncio.sleep
    +--> hashear: run_in_executor -> ProcessPoolExecutor
    |
    +-----------------------> TaskRegistry actualiza estado/resultado

Apagado: application.py/lifespan -> workers -> snapshots.py -> estado_<timestamp>.json
```

El flujo de una tarea es: `POST /tareas` valida la solicitud, crea un registro `pendiente` y encola su ID; un worker lo consume y pasa a `ejecutando`; el ejecutor despacha el trabajo según su tipo; al finalizar, el registro queda `completada`, `fallida` o `cancelada`. Las consultas HTTP leen el registro compartido.

## 3. Decisiones de diseño argumentadas

### ¿Por qué `asyncio.Queue` y no `queue.Queue`?

`asyncio.Queue` está diseñada para productores y consumidores que son corrutinas: `await queue.get()` suspende al worker cuando no hay elementos y permite que el event loop atienda otras tareas. En cambio, `queue.Queue.get()` es una operación bloqueante para threads; usarla directamente en una corrutina podría bloquear el event loop. Los workers y las rutas comparten el mismo event loop, y las operaciones breves del registro no contienen `await`; por eso esas modificaciones no se intercalan y no requieren un `Lock` explícito. `asyncio.Queue` no es una cola para compartir entre hilos del sistema operativo.

### ¿Cómo se evita que una tarea CPU-bound congele la API?

El hasheo se ejecuta mediante `loop.run_in_executor` con un `ProcessPoolExecutor`. El bucle de hashes corre en un proceso separado, de modo que el hilo del event loop puede continuar atendiendo rutas HTTP y otras corrutinas. `hash_text` divide las iteraciones en lotes acotados; espera cada lote y puede revisar una cancelación entre lotes. Esto no elimina el costo de CPU: el número de procesos y los recursos de la máquina limitan el throughput.

### ¿Cómo se implementó la cancelación y qué pasa con recursos en uso?

`DELETE /tareas/{id}` cambia directamente a `cancelada` una tarea todavía pendiente. Si está ejecutándose, cancela su corrutina y espera el `completion_event` antes de responder. El worker maneja `CancelledError`, actualiza el estado y limpia las referencias y el contador de workers en un `finally`.

Las descargas usan `async with` para cerrar la respuesta HTTP al terminar o cancelarse. En un hash, una llamada ya iniciada en el proceso hijo no se puede detener inmediatamente: `asyncio.shield` y la espera del lote actual permiten terminar ese lote antes de propagar la cancelación; no se envían más lotes. Al apagar, el `lifespan` cierra también el cliente HTTP y el `ProcessPoolExecutor`.

### ¿Qué pasa si un worker lanza una excepción no capturada?

Las excepciones normales (`Exception`) producidas por el procesador se capturan en `_execute`: la tarea se marca `fallida` con el motivo y el worker puede continuar con la siguiente. Si una excepción escapa de esa gestión —por ejemplo, ocurre fuera del bloque que la captura—, `_consume` ejecuta `queue.task_done()` en su `finally`, pero la corrutina worker termina. El sistema no tiene un supervisor que la reinicie automáticamente, por lo que puede quedar con menos workers disponibles. Esta es una limitación conocida.

## 4. Mediciones obligatorias

Las mediciones se pueden repetir desde la raíz del repositorio:

```bash
python -m tp2.benchmarks.measurements
```

El script inicia un servidor local temporal, ejecuta las tres pruebas y muestra el entorno y resultados como JSON. Sus rutas `/__benchmark/*` no forman parte de la API normal. El resultado completo de la corrida documentada está en [`benchmarks/validation-results.json`](benchmarks/validation-results.json).

**Entorno registrado:** Python 3.13.5, macOS 26.5.1 arm64, 4 workers y 2 procesos en el pool. Los tiempos dependen del equipo y pueden variar entre ejecuciones.

### Concurrencia I/O: 20 descargas

El servidor local de benchmark agrega 20 ms de espera asíncrona por respuesta. Se comparan 20 descargas secuenciales con las mismas 20 descargas concurrentes.

| Ejecución | Tiempo |
|---|---:|
| Secuencial | 0,4763 s |
| Concurrente | 0,0463 s |
| Speedup | **10,29×** |

Las esperas de red se solapan: el tiempo concurrente se acerca al de una espera, más el costo de las solicitudes locales, y no a la suma de las 20 esperas.

### Latencia del event loop durante CPU-bound

Se mide `GET /tareas` mientras el endpoint de benchmark calcula 750.000 hashes SHA-256 en línea o mediante `ProcessPoolExecutor`.

| Modo de hash | Latencia de `GET /tareas` | Tiempo de la solicitud de hash |
|---|---:|---:|
| Inline, sin executor | 255,8 ms | 291,6 ms |
| `ProcessPoolExecutor` | 19,1 ms | 501,1 ms |

El modo inline bloquea el event loop y demora la respuesta HTTP. Con executor, `GET /tareas` responde antes porque el cálculo se ejecuta en otro proceso. El tiempo total del hash con executor es mayor en esta medición e incluye el costo de coordinar el proceso; la comparación principal es la latencia de la API mientras el hash está en curso.

### Techo del pool

Se enviaron lotes crecientes de tareas `hashear`, de 500.000 iteraciones por tarea. Cada tiempo es la mediana de tres muestras, con cuatro workers de corrutinas y dos procesos.

| Tareas en el lote | Tiempo mediano | Throughput |
|---:|---:|---:|
| 1 | 0,2335 s | 4,28 tareas/s |
| 2 | 0,2401 s | 8,33 tareas/s |
| 4 | 0,4219 s | 9,48 tareas/s |
| 8 | 0,8355 s | 9,58 tareas/s |
| 16 | 1,6696 s | 9,58 tareas/s |

El throughput aumenta al pasar de uno a cuatro trabajos, pero se estabiliza cerca de **9,5–9,6 tareas/s** desde los lotes de cuatro. A partir de ese punto, agregar tareas aumenta la espera y el tiempo total, pero casi no agrega capacidad de procesamiento. En esta configuración, el cálculo CPU-bound y los dos procesos disponibles limitan el pool; el valor concreto también depende del hardware.

## 5. Conceptos del curso aplicados

- **Productor-consumidor y sincronización (Clase 11, `clase_11_sincronizacion`):** `POST /tareas` produce IDs en una `asyncio.Queue` compartida y las corrutinas de `WorkerPool` los consumen. Es el patrón productor-consumidor visto en clase, implementado con corrutinas en vez de threads. Las operaciones breves sobre el registro no tienen puntos de suspensión, así que no intercalan modificaciones y no necesitan un `Lock` explícito.
- **Multiplexing, corrutinas y red (Clases 17, 18 y 20):** `download_urls` usa `httpx.AsyncClient` y `asyncio.TaskGroup` para solapar esperas de red. Mientras una corrutina espera una respuesta, el event loop puede ejecutar otras. Esto conecta el I/O multiplexado con `async`/`await` y la programación asíncrona en red.
- **HTTP y FastAPI (Clase 19, `clase_19_http_fastapi`):** `api.py` define las rutas, recibe los modelos validados por Pydantic y devuelve respuestas HTTP. Por ejemplo, `POST /tareas` responde `202 Accepted` porque acepta el trabajo para procesarlo después.
- **Cancelación asíncrona (Clase 21, `clase_21_asyncio_avanzado`):** el endpoint de cancelación solicita la cancelación de la corrutina, y `hash_text` espera que termine el lote ya enviado al proceso antes de propagarla. Así se contempla que cancelar una corrutina no detiene instantáneamente un cálculo que ya está ejecutándose en otro proceso.
- **Ejecutores (Clase 22, `clase_22_concurrent_futures`):** `TaskExecutor.hash_text` delega lotes de SHA-256 con `loop.run_in_executor` y `ProcessPoolExecutor`. Esto evita ejecutar el cálculo intensivo en el event loop.

## 6. Limitaciones conocidas

- El registro operativo vive en memoria. El snapshot es para inspección y no restaura ni reanuda tareas al reiniciar.
- El registro y la cola son acotados; ante saturación se rechazan nuevas tareas con `429`, y los registros terminales antiguos pueden purgarse.
- El apagado solo espera hasta `TP2_SHUTDOWN_TIMEOUT_SECONDS`. Al vencer el plazo, cancela las tareas activas y guarda como `pendiente` las tareas que todavía no empezaron.
- La cancelación de un hash es cooperativa: el lote que ya se ejecuta en el proceso hijo termina antes de que se complete la cancelación.
- Si una excepción inesperada termina una corrutina worker fuera de la gestión normal de errores, no hay un supervisor que la reinicie.
- El servicio no incluye autenticación, reintentos automáticos, broker de mensajes ni coordinación entre varias instancias. La cola reside en una sola instancia del proceso.

## 7. Lo que aprendí

Al completar el TP2, aprendí que el event loop de `asyncio` permite manejar mucha
concurrencia con un solo hilo siempre y cuando las tareas no bloqueen el loop con
operaciones síncronas. Descubrí que las tareas CPU-bound, como el hasheo, deben
ejecutarse en un `ProcessPoolExecutor` para no congelar la API, y que la
cancelación cooperativa requiere cuidado: hay que esperar a que los lotes
terminen antes de propagarla. También entendí la importancia de los snapshots
al apagar el servicio, porque permiten inspeccionar el estado de las tareas
después del apagado, y que limitar la cantidad de tareas retenidas evita un
crecimiento ilimitado del uso de memoria, aunque las tareas terminales antiguas
puedan eliminarse para liberar espacio.
