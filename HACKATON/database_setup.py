import mysql.connector
import os

# --- 1. CONFIGURACIÓN DE LA BASE DE DATOS ---
# Asegúrate de que estas variables coincidan con las de tu app.py

DB_NAME = os.environ.get('DB_NAME', 'hackathon_db')
DB_USER = os.environ.get('DB_USER', 'root')
# ¡¡¡REEMPLAZA ESTO con tu contraseña real de MySQL!!!
DB_PASSWORD = os.environ.get('DB_PASSWORD', '') 
DB_HOST = os.environ.get('DB_HOST', 'localhost')

def setup_database():
    """
    Crea la base de datos y la tabla 'users' si no existen.
    """
    try:
        # Paso 1: Conectarse a MySQL (sin una base de datos específica)
        print(f"Paso 1: Conectando a MySQL en {DB_HOST} como {DB_USER}...")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        print(" -> Conexión exitosa.")

        # Paso 2: Crear la base de datos si no existe
        print(f"Paso 2: Asegurando que la base de datos '{DB_NAME}' exista...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f" -> Base de datos '{DB_NAME}' asegurada.")
        
        # Cerrar la conexión inicial
        cursor.close()
        conn.close()

        # Paso 3: Conectarse a la base de datos específica 'hackathon_db'
        print(f"Paso 3: Conectando a la base de datos '{DB_NAME}'...")
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        print(" -> Conexión exitosa.")

        # Paso 4: Crear la tabla 'users' si no existe
        print("Paso 4: Asegurando que la tabla 'users' exista...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)
        print(" -> Tabla 'users' asegurada.")
        
        print("\n¡ÉXITO! Configuración de base de datos finalizada.")

    except mysql.connector.Error as err:
        print("\n--- ¡ERROR! ---")
        if err.errno == 1045: # Código de error para 'Access denied'
            print(f"ERROR CRÍTICO: 'Access denied' para el usuario '{DB_USER}'@'{DB_HOST}'.")
            print("Por favor, revisa tu DB_USER y DB_PASSWORD en el archivo 'database_setup.py'.")
        elif err.errno == 2003: # Código de error para 'Can't connect'
             print(f"ERROR CRÍTICO: No se pudo conectar a MySQL en '{DB_HOST}'.")
             print("¿Está tu servidor de MySQL (XAMPP, MAMP, etc.) corriendo?")
        else:
            print(f"Error inesperado de MySQL: {err}")
    finally:
        # Asegurarse de que todo se cierre
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()
            print("Conexión cerrada.")

# Ejecutar la función de configuración
if __name__ == '__main__':
    setup_database()