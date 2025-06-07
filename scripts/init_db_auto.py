"""
Automated setup script to create the initial database and tables
This version uses environment variables instead of user input
"""

import os
import sys

# Add the app directory to Python path for imports
sys.path.insert(0, "/app")

from sqlmodel import Session, select
from app.database.connection import engine, create_db_and_tables
from app.database.models import User, Client
from app.core.security import get_password_hash


def create_initial_data():
    print("Creating database and tables...")
    create_db_and_tables()

    with Session(engine) as session:
        # Create a default admin user
        admin_user = session.exec(select(User).where(User.username == "admin")).first()
        if not admin_user:
            print("Creating admin user...")
            admin_username = os.environ.get("ADMIN_USERNAME", "admin")
            admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

            admin_account = User(
                username=admin_username,
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                role="Admin",
            )
            session.add(admin_account)
            session.commit()
            session.refresh(admin_account)
            print(f"Admin user '{admin_username}' created successfully")
        else:
            print("Admin user already exists, skipping creation")

        # Create a default client "Personal" so you can create cases without a real client attached
        client1 = session.exec(select(Client).where(Client.name == "Personal")).first()
        if not client1:
            print("Creating default 'Personal' client...")
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@owlculus.local")
            client1 = Client(name="Personal", email=admin_email)
            session.add(client1)
            session.commit()
            session.refresh(client1)
            print("Default 'Personal' client created successfully")
        else:
            print("Default 'Personal' client already exists, skipping creation")

    print("Database initialization completed successfully!")


if __name__ == "__main__":
    create_initial_data()
