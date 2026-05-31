from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Only create if they don't exist
    if not User.query.filter_by(username="recepcion").first():
        recep = User(
            username="recepcion",
            password_hash=generate_password_hash("recepcion123"),
            role="receptionist"
        )
        db.session.add(recep)

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="supervisor"
        )
        db.session.add(admin)


    db.session.commit()
