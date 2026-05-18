from flask import Flask, render_template, request, jsonify
import xmlrpc.client
import os  # <-- NUEVO: Importamos la librería os

app = Flask(__name__)

# Configuración Odoo usando Variables de Entorno
# Si la variable no existe, el programa fallará, lo cual es por seguridad.
URL = os.environ.get('ODOO_URL')
DB = os.environ.get('ODOO_DB')
USER = os.environ.get('ODOO_USER')
PASS = os.environ.get('ODOO_PASS')

# Variables globales para la sesión de Odoo
odoo_uid = None
odoo_models = None

def get_odoo_connection():
    """Obtiene y reutiliza la conexión a Odoo para maximizar la velocidad."""
    global odoo_uid, odoo_models
    
    try:
        if not odoo_uid:
            common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
            odoo_uid = common.authenticate(DB, USER, PASS, {})
            if odoo_uid:
                odoo_models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
        return odoo_uid, odoo_models
    except Exception as e:
        odoo_uid = None
        raise e

def format_order_name(name):
    """Normaliza el nombre de la orden a SOXXXXXXX"""
    clean_name = name.strip().upper()
    if not clean_name.startswith('SO') and clean_name:
        clean_name = f"SO{clean_name}"
    return clean_name

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
def home():
    """Página principal con selección de Marketplace"""
    return render_template('home.html')

@app.route('/falabella')
def falabella():
    """Verificador estilo Falabella"""
    return render_template('falabella.html')

@app.route('/mercadolibre')
def mercadolibre():
    """Verificador estilo Mercado Libre"""
    return render_template('mercadolibre.html')

@app.route('/ripley')
def ripley():
    """Verificador estilo Ripley (aún no implementado)"""
    return render_template('ripley.html')

# --- LÓGICA DE NEGOCIO (API) ---

@app.route('/verify', methods=['POST'])
def verify():
    """Verificador para Falabella"""
    global odoo_uid
    data = request.json
    order_name = format_order_name(data.get('name', ''))
    client_ref = data.get('client_ref', '').strip()
    
    try:
        uid, models = get_odoo_connection()
        if not uid:
            return {"status": "error", "message": "Fallo de autenticación en Odoo."}

        domain = [['name', '=', order_name], ['client_order_ref', '=', client_ref]]
        orders = models.execute_kw(DB, uid, PASS, 'sale.order', 'search_read', [domain], {
            'fields': ['partner_id'],
            'limit': 1
        })

        if orders:
            return {"status": "success", "message": f"¡Coincidencia! Cliente: {orders[0]['partner_id'][1]}"}
        else:
            return {"status": "error", "message": f"No se encontró la orden {order_name} con esa referencia."}
            
    except Exception as e:
        odoo_uid = None
        return {"status": "error", "message": f"Error de conexión: {str(e)}"}

@app.route('/verify_meli', methods=['POST'])
def verify_meli():
    """Verificador para Mercado Libre con dos campos: SO y Shipping ID."""
    global odoo_uid
    data = request.json
    order_name = format_order_name(data.get('name', ''))
    shipping_id = data.get('shipping_id', '').strip()

    if not order_name or not shipping_id:
        return jsonify({"status": "error", "message": "Debe escanear la Orden y el Shipping ID."}), 400

    try:
        uid, models = get_odoo_connection()
        if not uid:
            return jsonify({"status": "error", "message": "Fallo de autenticación en Odoo."})

        # Buscar la orden que coincida con AMBOS campos
        domain = [
            ['name', '=', order_name],
            ['shipping_id_meli', '=', shipping_id]
        ]
        
        orders = models.execute_kw(DB, uid, PASS, 'sale.order', 'search_read', [domain], {
            'fields': ['name'],
            'limit': 1
        })

        if orders:
            return jsonify({"status": "success", "message": f"¡Coincidencia! La orden {order_name} es correcta."})
        else:
            # Si no hay coincidencia, dar un mensaje de error específico
            return jsonify({"status": "error", "message": f"Error: La orden {order_name} no corresponde al Shipping ID escaneado."})

    except Exception as e:
        odoo_uid = None
        return jsonify({"status": "error", "message": f"Error de conexión con Odoo: {str(e)}"})


# --- EJECUCIÓN DEL SERVIDOR ---

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
