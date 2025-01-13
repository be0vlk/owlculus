"""
Setup script to create the initial database and tables
"""

import os
import sys

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, project_root)

from sqlmodel import Session, select
from backend.app.database.connection import engine, create_db_and_tables
from backend.app.database.models import User, Client
from backend.app.core.security import get_password_hash


def create_initial_data():
    create_db_and_tables()

    with Session(engine) as session:
        # Create a default admin user
        admin_user = session.exec(select(User).where(User.username == "admin")).first()
        if not admin_user:
            print("Create the admin user...\n")
            admin_username = input(str("Username for admin user: "))
            admin_password = input(str("Password for admin user: "))
            admin_email = input(str("Email address for admin user: "))
            admin_account = User(
                username=admin_username,
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                role="Admin",
            )
            session.add(admin_account)
            session.commit()
            session.refresh(admin_account)

        # Create a default client "Personal" so you can create cases without a real client attached
        client1 = session.exec(select(Client).where(Client.name == "Personal")).first()
        if not client1:
            client1 = Client(
                name="Personal", email=admin_email
            )
            session.add(client1)
            session.commit()
            session.refresh(client1)


if __name__ == "__main__":
    create_initial_data()
