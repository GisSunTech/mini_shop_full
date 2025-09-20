from models import db, User
from config import Config
from werkzeug.security import generate_password_hash
from flask import Flask

def create_admin():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()  # Ensure tables exist

        admin_email = app.config['ADMIN_EMAIL']
        admin_password = app.config['ADMIN_PASSWORD']

        # Check if admin already exists
        existing_admin = User.query.filter_by(email=admin_email).first()
        if existing_admin:
            print(f"Admin user {admin_email} already exists.")
            return

        # Create new admin
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user {admin_email} created successfully.")

if __name__ == "__main__":
    create_admin()
