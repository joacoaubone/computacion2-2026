# Dudas

### Diferencia entre `shutdown_event.wait(timeout=X)` y `time.sleep(X)`

- `time.sleep(X)` duerme el proceso por X segundos sin posibilidad de interrumpirlo antes.
- `shutdown_event.wait(timeout=X)` duerme por X segundos pero se despierta al instante si otro proceso hace `shutdown_event.set()`.
- En el monitor usamos `wait(timeout=)` para que los procesos hijos reaccionen inmediatamente a una señal de shutdown, sin tener que esperar a que termine su sleep.
