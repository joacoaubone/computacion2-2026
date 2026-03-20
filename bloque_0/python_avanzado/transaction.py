class Transaction:
    def __init__(self, objeto):
        self.objeto = objeto
        self.estado_inicial = None

    def __enter__(self):
        """ Guardar copia del estado del objeto """
        self.estado_inicial = vars(self.objeto).copy()
        return self.objeto

    def __exit__(self, tipo_exc, valor_exc, traceback):
        """ Si hubo excepción revertir """
        if tipo_exc is not None:
            vars(self.objeto).clear()
            vars(self.objeto).update(self.estado_inicial)
            
        return False
    
class Cuenta:
    def __init__(self, saldo):
        self.saldo = saldo
        self.nombre = "Sin nombre"

cuenta = Cuenta(1000)

# Transacción exitosa
with Transaction(cuenta):
    cuenta.saldo -= 100
    cuenta.saldo -= 200

print(cuenta.saldo)  # 700

# Transacción que falla
try:
    with Transaction(cuenta):
        cuenta.saldo -= 100
        cuenta.nombre = "Test"
        raise ValueError("Error simulado")
except ValueError:
    pass

print(cuenta.saldo)  # 700 (se revirtió)
print(cuenta.nombre)  # "Sin nombre" (también se revirtió)