import mysql.connector
from datetime import datetime
import json
from decimal import Decimal

# conexion a base de datos por XAMPP
db_config = {
    'host': 'localhost',
    'user': 'root', 
    'password': '', 
    'database': 'gestion_gastos'
}

# pasar los decimales a float
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# conectar a base datos
def get_connection():
    conn = mysql.connector.connect(**db_config)
    return conn

# completar los numeros
def format_department_id(depto_id):
    return str(depto_id).zfill(3)  

#  validar fechas
def validar_fecha(fecha):
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
        return True
    except ValueError:
        return False

#  generar gastos comunes
def generar_gastos_comunes(año, mes=None, monto_default=50000):
    conn = get_connection()
    cursor = conn.cursor()
    
    if not mes:  
        for m in range(1, 13):
            _generar_gastos_por_mes(cursor, año, m, monto_default)
    else:  
        _generar_gastos_por_mes(cursor, año, mes, monto_default)

    conn.commit()
    cursor.close()
    conn.close()
    return {"estado": "Gastos generados exitosamente"}

def _generar_gastos_por_mes(cursor, año, mes, monto_default):
    cursor.execute("SELECT id FROM departamentos")
    departamentos = cursor.fetchall()
    
    for (depto_id,) in departamentos:
        cursor.execute("""
            INSERT INTO gastos_comunes (departamento_id, año, mes, monto)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE monto = %s
        """, (depto_id, año, mes, monto_default, monto_default))

# registrar pago
def registrar_pago(departamento, año, mes, fecha_pago):
    if not validar_fecha(fecha_pago):
        return {"estado": "Fecha inválida. Formato requerido: YYYY-MM-DD"}

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    departamento_id = format_department_id(departamento)

    cursor.execute("""
        SELECT id, pagado FROM gastos_comunes
        WHERE departamento_id = %s AND año = %s AND mes = %s
    """, (departamento_id, año, mes))
    gasto = cursor.fetchone()

    if not gasto:
        cursor.close()
        conn.close()
        return {"estado": "Gasto no encontrado"}

    gasto_id, pagado = gasto["id"], gasto["pagado"]
    if pagado:
        cursor.close()
        conn.close()
        return {"estado": "Pago duplicado"}

    fecha_limite = datetime(año, mes, 15)
    fecha_pago_dt = datetime.strptime(fecha_pago, "%Y-%m-%d")
    estado_pago = "Pago dentro del plazo" if fecha_pago_dt <= fecha_limite else "Pago fuera del plazo"

    cursor.execute("""
        UPDATE gastos_comunes
        SET pagado = TRUE, mes_pago = %s
        WHERE id = %s
    """, (fecha_pago_dt.month, gasto_id))

    conn.commit()
    cursor.close()
    conn.close()
    return {"estado": estado_pago, "departamento": departamento_id, "fecha_pago": fecha_pago}

#  listar pendientes
def listar_pendientes(hasta_año, hasta_mes):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT departamento_id, año, mes, monto
        FROM gastos_comunes
        WHERE pagado = FALSE AND (año < %s OR (año = %s AND mes <= %s))
        ORDER BY año, mes
    """, (hasta_año, hasta_año, hasta_mes))
    pendientes = cursor.fetchall()

    #  pasar decimal a float
    for pendiente in pendientes:
        pendiente["monto"] = float(pendiente["monto"])

    cursor.close()
    conn.close()

    if not pendientes:
        return {"estado": "Sin montos pendientes"}
    return pendientes

# resumen de un departamento
def consultar_gastos_departamento(departamento):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    departamento_id = format_department_id(departamento)

    cursor.execute("""
        SELECT año, mes, monto, pagado, mes_pago
        FROM gastos_comunes
        WHERE departamento_id = %s
        ORDER BY año, mes
    """, (departamento_id,))
    gastos = cursor.fetchall()

    # pasa decimal a float
    for gasto in gastos:
        gasto["monto"] = float(gasto["monto"])

    cursor.close()
    conn.close()

    if not gastos:
        return {"estado": "Sin registros"}
    return gastos

#  detalle de un departamento
def mostrar_gastos_departamento(departamento):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    departamento_id = format_department_id(departamento)

    cursor.execute("""
        SELECT d.nombre, gc.año, gc.mes, gc.monto, gc.pagado, gc.mes_pago
        FROM gastos_comunes gc
        JOIN departamentos d ON gc.departamento_id = d.id
        WHERE gc.departamento_id = %s
        ORDER BY gc.año, gc.mes
    """, (departamento_id,))
    gastos = cursor.fetchall()

    # pasar decimal a float
    for gasto in gastos:
        gasto["monto"] = float(gasto["monto"])

    cursor.close()
    conn.close()

    # no hay registros
    if not gastos:
        return f"El departamento {departamento} no tiene registros de gastos."

    # formatear la salida
    salida = [f"Gastos del {gastos[0]['nombre']} (ID: {departamento_id}):\n"]
    for gasto in gastos:
        estado = "Pagado" if gasto["pagado"] else "Pendiente"
        mes_pago = f", Mes de Pago: {gasto['mes_pago']}" if gasto["pagado"] else ""
        salida.append(f"  - Año: {gasto['año']}, Mes: {gasto['mes']}, Monto: ${gasto['monto']:.2f} ({estado}{mes_pago})")

    return "\n".join(salida)


def menu():
    while True:
        print("\n=== Gestión de Gastos Comunes ===")
        print("1. Generar gastos comunes")
        print("2. Registrar pago")
        print("3. Listar gastos pendientes")
        print("4. Consultar resumen de un departamento")
        print("5. Consultar detalle de gastos de un departamento")
        print("6. Salir")

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            año = int(input("Ingrese el año: "))
            mes = input("Ingrese el mes (opcional, presione Enter para todo el año): ")
            monto = int(input("Ingrese el monto por departamento: "))
            mes = int(mes) if mes else None
            print(json.dumps(generar_gastos_comunes(año, mes, monto), indent=4, cls=DecimalEncoder))

        elif opcion == "2":
            depto = input("Ingrese el número de departamento: ")
            año = int(input("Ingrese el año: "))
            mes = int(input("Ingrese el mes: "))
            fecha_pago = input("Ingrese la fecha de pago (YYYY-MM-DD): ")
            print(json.dumps(registrar_pago(depto, año, mes, fecha_pago), indent=4, cls=DecimalEncoder))

        elif opcion == "3":
            año = int(input("Ingrese el año: "))
            mes = int(input("Ingrese el mes hasta el cual desea listar pendientes: "))
            print(json.dumps(listar_pendientes(año, mes), indent=4, cls=DecimalEncoder))

        elif opcion == "4":
            depto = input("Ingrese el número de departamento: ")
            print(json.dumps(consultar_gastos_departamento(depto), indent=4, cls=DecimalEncoder))

        elif opcion == "5":
            depto = input("Ingrese el número de departamento: ")
            print(mostrar_gastos_departamento(depto))

        elif opcion == "6":
            print("¡Hasta luego!")
            break

        else:
            print("Opción inválida. Intente nuevamente.")

if __name__ == "__main__":
    menu()
