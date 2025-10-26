from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
import mysql.connector
import bcrypt
import os
import requests
import json
from datetime import timedelta
from functools import wraps



DB_NAME = os.environ.get('DB_NAME', 'hackathon_db')
DB_USER = os.environ.get('DB_USER', 'root') 
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost') 
NESSIE_API_KEY = os.environ.get('NESSIE_API_KEY', "9203847529304875")
NESSIE_API_BASE = "http://api.reimaginebanking.com" 


app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_secreta_muy_dificil_de_adivinar_para_el_hackathon')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1) 


CORS(app, origins=["null", "http://127.0.0.1:5500", "http://localhost:5500"], supports_credentials=True) 

print("--- Iniciando Servidor Flask (Modo CON-DB) ---")



def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("DEBUG: Conexión a MySQL exitosa.")
        return conn
    except mysql.connector.Error as err:
        print(f"ERROR: No se pudo conectar a MySQL: {err}")
        if err.errno == 1049:
             print("ERROR CRÍTICO: La base de datos 'hackathon_db' no existe.")
             print("Por favor, ejecuta 'python database_setup.py' primero.")
        elif err.errno == 1045:
             print("ERROR CRÍTICO: 'Access denied'. Revisa tu DB_USER y DB_PASSWORD en app.py.")
        return None


@app.route('/register', methods=['POST'])
def register():
    print("DEBUG: Recibida petición en /register")
    data = request.get_json()
    username = data.get('username', 'Usuario')
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email y contraseña son requeridos"}), 400

    hashed_password_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    hashed_password_str = hashed_password_bytes.decode('utf-8')

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Error interno del servidor (DB)"}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"message": "El email ya está registrado"}), 409
        
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, hashed_password_str)
        )
        conn.commit()
        print(f"DEBUG: Usuario {email} registrado exitosamente.")
        return jsonify({"message": "Usuario registrado exitosamente"}), 201
    
    except mysql.connector.Error as err:
        print(f"ERROR en /register: {err}")
        return jsonify({"message": "Error al registrar el usuario en la DB"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    print("DEBUG: Recibida petición en /login")
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email y contraseña son requeridos"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Error interno del servidor (DB)"}), 500
    
    cursor = conn.cursor(dictionary=True) 
    
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session.permanent = True
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            print(f"DEBUG: Usuario {email} inició sesión. ID de sesión: {session['user_id']}")
            return jsonify({"message": "Inicio de sesión exitoso", "email": user['email']}), 200
        else:
            print(f"DEBUG: Fallo de login para {email}. Email o contraseña incorrectos.")
            return jsonify({"message": "Email o contraseña incorrectos"}), 401 
    
    except mysql.connector.Error as err:
        print(f"ERROR en /login: {err}")
        return jsonify({"message": "Error al verificar el usuario en la DB"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/logout', methods=['POST'])
def logout():
    print(f"DEBUG: Recibida petición en /logout para usuario ID: {session.get('user_id')}")
    session.pop('user_id', None)
    session.pop('user_email', None)
    return jsonify({"message": "Sesión cerrada"}), 200

@app.route('/check_session', methods=['GET'])
def check_session():
    if 'user_id' in session and 'user_email' in session:
        print(f"DEBUG: Sesión activa verificada para: {session['user_email']}")
        return jsonify({"logged_in": True, "email": session['user_email']}), 200
    else:
        print("DEBUG: No se encontró sesión activa.")
        return jsonify({"logged_in": False}), 401



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            print(f"ADVERTENCIA: Acceso no autorizado a {f.__name__}. No hay user_id en la sesión.")
            return jsonify({"message": "Acceso no autorizado. Inicia sesión."}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/get_debts', methods=['GET'])
@login_required
def get_debts():
    user_email = session.get('user_email', '???')
    print(f"DEBUG: Recibida petición en /get_debts de usuario: {user_email}")

    
    customer_id_to_fetch = os.environ.get('NESSIE_CUSTOMER_ID', 'CUSTOMER_ID_DE_PRUEBA') 
    debts_from_api = []
    
    try:
        url = f'{NESSIE_API_BASE}/customers/{customer_id_to_fetch}/accounts?key={NESSIE_API_KEY}'
        headers = {'Accept': 'application/json'}
        print(f"DEBUG: Llamando a API de Nessie en {url[:60]}...") 
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        api_data = response.json()
        print("DEBUG: Respuesta de Nessie recibida.")
        
        for account in api_data:
            if account.get('type') in ['Credit Card', 'Loan']:
                balance = float(account.get('balance', 0.0))
                interest_rate = 0.0
                min_payment = 0.0

                if account.get('type') == 'Credit Card':
                    interest_rate = float(account.get('apr', 0.28))
                    min_payment = max(25.0, balance * 0.01)
                elif account.get('type') == 'Loan':
                    interest_rate = float(account.get('interest_rate', 0.075))
                    min_payment = float(account.get('monthly_payment', 150.0))

                if balance > 0:
                    debts_from_api.append({
                        "id": account['_id'],
                        "name": account.get('nickname', 'Cuenta de Deuda'),
                        "balance": balance,
                        "interest_rate": interest_rate,
                        "min_payment": min_payment
                    })
        
        if debts_from_api:
            print(f"DEBUG: Devolviendo {len(debts_from_api)} deudas desde API Nessie.")
            return jsonify(debts_from_api), 200
            
    except requests.exceptions.RequestException as e:
        print(f"ADVERTENCIA: Fallo en la llamada a la API de Nessie. Usando datos simulados. Error: {e}")

    debts_simulated = [
        {"id": "c1", "name": "Tarjeta Platinum (Simulada)", "balance": 4500.00, "interest_rate": 0.28, "min_payment": 150.00},
        {"id": "c2", "name": "Préstamo Personal Auto (Simulada)", "balance": 12000.00, "interest_rate": 0.075, "min_payment": 400.00},
        {"id": "c3", "name": "Préstamo Estudiantil (Simulada)", "balance": 800.00, "interest_rate": 0.04, "min_payment": 50.00}
    ]
    print(f"DEBUG: Devolviendo {len(debts_simulated)} deudas simuladas (fallback).")
    return jsonify(debts_simulated), 200



@app.route('/calculate', methods=['POST'])
@login_required
def calculate_debt_strategy():
    user_email = session.get('user_email', '???')
    print(f"DEBUG: Recibida petición en /calculate de usuario: {user_email}")
    
    try:
        data = request.get_json()
        strategy = data.get('strategy')
        extra_budget = float(data.get('extra_budget', 0))
        debts = data.get('debts', [])

        if not debts:
            return jsonify({"message": "No hay deudas para calcular"}), 400
    except Exception as e:
        print(f"Error parseando JSON de entrada: {e}")
        return jsonify({"message": "JSON de entrada inválido"}), 400

    def simulate_payment(debts, extra_budget, strategy):

        current_debts = json.loads(json.dumps(debts)) 
        
        if strategy == 'avalanche':
            current_debts.sort(key=lambda x: x['interest_rate'], reverse=True)
        else:
            current_debts.sort(key=lambda x: x['balance'])
        
        total_time_months = 0
        total_interest_paid = 0
        rolling_extra_payment = float(extra_budget)
        payment_plan = []
        
        total_initial_balance = sum(d['balance'] for d in debts)
        total_min_payments = sum(d['min_payment'] for d in debts)

        current_debts = [d for d in current_debts if d['balance'] > 0]

        while sum(d['balance'] for d in current_debts) > 0 and total_time_months < 120:
            total_time_months += 1
            
            payment_this_month = 0.0
            for debt in current_debts:
                monthly_interest = debt['balance'] * (debt['interest_rate'] / 12)
                total_interest_paid += monthly_interest
                debt['balance'] += monthly_interest
                
                payment_applied = min(debt['balance'], debt['min_payment'])
                debt['balance'] = max(0, debt['balance'] - payment_applied)
                payment_this_month += payment_applied

            available_extra = rolling_extra_payment
            
            for debt in current_debts:
                if available_extra <= 0:
                    break
                
                payment_applied = min(debt['balance'], available_extra)
                debt['balance'] -= payment_applied
                available_extra -= payment_applied
                
                if debt['balance'] <= 0:
                    rolling_extra_payment += debt['min_payment']
                    payment_plan.append({
                        "debt": debt['name'],
                        "month_paid": total_time_months,
                    })
            
            current_debts = [d for d in current_debts if d['balance'] > 0]
            
            if strategy == 'avalanche':
                current_debts.sort(key=lambda x: x['interest_rate'], reverse=True)
            else:
                current_debts.sort(key=lambda x: x['balance'])

            if not current_debts:
                break
        
        base_time_months = 0
        base_balance = total_initial_balance
        if total_min_payments > 0:
            avg_rate = sum(d['interest_rate'] for d in debts) / len(debts) if debts else 0.05
            while base_balance > 0 and base_time_months < 120:
                base_balance += base_balance * (avg_rate / 12)
                base_balance -= total_min_payments
                base_time_months += 1
        
        months_saved = max(0, base_time_months - total_time_months)
        interest_saved_dollars = (base_time_months * total_min_payments * 0.15) - (total_time_months * (total_min_payments + extra_budget) * 0.10)
        interest_saved_dollars = max(0, interest_saved_dollars)

        return {
            "strategy": strategy,
            "total_time_months": total_time_months if total_time_months < 120 else 120,
            "months_saved": months_saved,
            "total_interest_paid": total_interest_paid,
            "interest_saved_dollars": interest_saved_dollars,
            "payment_plan": payment_plan
        }

    try:
        results = simulate_payment(debts, extra_budget, strategy)
        print("DEBUG: Simulación calculada exitosamente.")
        return jsonify(results), 200
    except Exception as e:
        print(f"Error en la simulación: {e}")
        return jsonify({"message": "Error al procesar la simulación"}), 500


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    print(f"--- Iniciando servidor en {host}:5000 ---")
    app.run(debug=True, host=host, port=5000)
