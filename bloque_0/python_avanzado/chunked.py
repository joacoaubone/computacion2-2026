def chunked(iterable, size):
    it = iter(iterable)

    while True:
        chunk = []

        try:
            for _ in range(size):
                chunk.append(next(it))
        except StopIteration:
            if chunk:
                yield chunk
            break

        yield chunk

def procesar_batch(batch):
    print("Procesando batch:", batch)
    
# Dividir en grupos de 3
list(chunked(range(10), 3))
# [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

# Funciona con cualquier iterable
list(chunked("abcdefgh", 3))
# [['a', 'b', 'c'], ['d', 'e', 'f'], ['g', 'h']]

print(list(chunked(range(10), 3)))
print(list(chunked("abcdefgh", 3)))

# Caso práctico: procesar archivo grande en batches
def procesar_archivo_grande(path, batch_size=1000):
    with open(path) as f:
        for batch in chunked(f, batch_size):
            procesar_batch(batch)