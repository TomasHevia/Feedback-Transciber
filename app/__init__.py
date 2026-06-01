import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///complaints.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_AUDIO_SIZE_MB", 25)) * 1024 * 1024

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    CATEGORY_LABELS = {
        'ruido': 'Ruido', 'limpieza': 'Limpieza', 'facturacion': 'Facturación',
        'temperatura': 'Temperatura', 'mantenimiento': 'Mantenimiento',
        'internet_wifi': 'WiFi / Internet', 'television': 'Televisión',
        'electricidad': 'Electricidad', 'agua': 'Agua', 'plomeria': 'Plomería',
        'check_in': 'Ingreso', 'check_out': 'Salida', 'reserva': 'Reserva',
        'sobreventa': 'Sobreventa', 'habitacion_incorrecta': 'Hab. incorrecta',
        'llaves_acceso': 'Llaves / Acceso', 'equipaje': 'Equipaje',
        'estacionamiento': 'Estacionamiento', 'transporte': 'Transporte',
        'restaurante': 'Restaurante', 'desayuno': 'Desayuno',
        'room_service': 'Servicio a la habitación', 'servicio_no_atendido': 'Sin atención',
        'personal': 'Personal', 'seguridad': 'Seguridad',
        'cobro_indebido': 'Cobro indebido', 'reembolso': 'Reembolso',
        'amenidades': 'Amenidades', 'piscina': 'Piscina',
        'gimnasio': 'Gimnasio', 'accesibilidad': 'Accesibilidad', 'otro': 'Otro',
    }
    STATUS_LABELS = {
        'pending': 'Procesando…', 'processed': 'Sin revisar',
        'reviewed': 'Cerrado', 'error': 'Error',
    }
    app.jinja_env.filters['category_label'] = lambda c: CATEGORY_LABELS.get(c, c or '—')
    app.jinja_env.filters['status_label'] = lambda s: STATUS_LABELS.get(s, s or '—')

    from app.routes import main, api
    from app.auth import auth
    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth, url_prefix="/auth")

    with app.app_context():
        db.create_all()

    return app
