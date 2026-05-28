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

    from app.routes import main, api
    app.register_blueprint(main)
    app.register_blueprint(api, url_prefix="/api")

    with app.app_context():
        db.create_all()

    return app
