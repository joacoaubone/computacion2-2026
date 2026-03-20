def fibonacci(limite=None):
    a = 0
    b = 1
    while True:
        if limite is not None and a > limite:
            break
        yield a
        a, b = b, a + b

for n in fibonacci(limite=1000):
    print(n)
