class BufferedReader:
    def __init__(self, path, buffer_size=8192, encoding="utf-8"):
        self.path = path
        self.buffer_size = buffer_size
        self.encoding = encoding
        self.file = None
        self.buffer = ""

    def __enter__(self):
        self.file = open(self.path, "r", encoding=self.encoding)
        self.buffer = ""
        return self

    def __exit__(self, tipo_exc, valor_exc, traceback):
        if self.file is not None:
            self.file.close()
        return False

    def __iter__(self):
        if self.file is None:
            self.file = open(self.path, "r", encoding=self.encoding)
            self.buffer = ""

        while True:
            chunk = self.file.read(self.buffer_size)

            if not chunk:
                if self.buffer:
                    yield self.buffer
                    self.buffer = ""
                break

            self.buffer += chunk

            while "\n" in self.buffer:
                linea, self.buffer = self.buffer.split("\n", 1)
                yield linea + "\n"

        if self.file is not None and not self.file.closed:
            self.file.close()

with open("archivo_enorme.txt", "w") as f:
    f.write("INFO inicio\n")
    f.write("ERROR fallo 1\n")
    f.write("INFO sigue\n")
    f.write("ERROR fallo 2\n")

# El archivo tiene 1GB, pero solo usamos unos KB de memoria
for linea in BufferedReader("archivo_enorme.txt", buffer_size=8192):
    if "ERROR" in linea:
        print("Error encontrado:", linea)

# También debería funcionar como context manager
with BufferedReader("archivo_enorme.txt") as reader:
    for linea in reader:
        print(linea)