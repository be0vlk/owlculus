import argparse
import os
from dotenv import load_dotenv
import subprocess
from werkzeug.security import generate_password_hash
from .db import db
from .models import User
from .helpers import printc
import secrets
from openai import OpenAI
from dotenv import set_key, find_dotenv


def migrate_db(initial=True):

    try:
        if initial:
            subprocess.run(["python3", "-m", "flask", "db", "init"])
            comment = "Initial migration"
        else:
            comment = "DB Update Migration"
        subprocess.run(["python3", "-m", "flask", "db", "migrate", "-m", f"{comment}"])
        subprocess.run(["python3", "-m", "flask", "db", "upgrade"])
        printc("[*] Migration completed")
    except Exception as e:
        printc(f"[!] Error with migration: {e}")


def generate_secret_key():
    """
    Generates a random secret key used by the app and as the JWT secret for authentication.
    """
    secret = str(secrets.token_urlsafe(18))
    set_key(find_dotenv(), "APP_SECRET_KEY", secret)

    return


def create_admin_user(app):
    """
    This function creates an Admin user with the username 'admin' and a generated password.
    Feel free to change the default admin username via the 'admin_username' variable.
    You may also want to change the email in the admin_user/User object.
    """
    admin_username = "admin"
    admin_password = str(secrets.token_urlsafe(18))
    hashed_password = generate_password_hash(admin_password)

    admin_user = User(
        username=admin_username,
        password=hashed_password,
        email="fake@example.com",
        role="admin",
    )
    with app.app_context():
        try:
            db.session.add(admin_user)
            db.session.commit()

            printc(
                f"""
            ____________________________________________________________________________________

            [+] ADMIN USER CREATED WITH PASSWORD: {admin_password}
            ____________________________________________________________________________________
            """
            )
        except Exception as e:
            printc(f"[!] Failed to add user {admin_username}. Error: {e}")


def create_gpt_assistant():
    """
    Creates the 'Strixy' ChatGPT custom assistant used in api.tools.strixy.
    Change the instructions, aka system prompt, here if you so desire.
    """

    client = OpenAI()
    printc("[*] Creating GPT Assistant")
    assistant = client.beta.assistants.create(
        name="Test",
        instructions="Your name is Strixy. You're an OSINT Analyst that specializes in identifying patterns, "
        "generating innovative leads, and deducing new areas of inquiry from various data sources. "
        "You use your broad skill set to analyze structured and unstructured data, offering insights "
        "and suggestions for further investigation by thinking outside-the-box. Maintain a "
        "professional, formal approach, ensuring that analysis is factual and unbiased.",
        tools=[{"type": "code_interpreter"}, {"type": "retrieval"}],
        model="gpt-4-turbo-preview",  # You may want to change this for cost or performance reasons
    )
    set_key(find_dotenv(), "GPT_ASSISTANT_ID", assistant.id)

    return


def run_setup(app):
    try:
        generate_secret_key()
        load_dotenv()
        migrate_db()
        create_admin_user(app)
        if os.getenv("OPENAI_API_KEY") and not os.getenv("GPT_ASSISTANT_ID"):
            create_gpt_assistant()
        else:
            printc(
                "[*] Skipping GPT Assistant creation because it already exists or OPENAI_API_KEY not set in .env"
            )
    except Exception as e:
        printc(f"[!] Error with automated setup via app_setup.py: {e}")
        exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database setup script")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run database migration if there has been a model update",
    )
    parser.add_argument(
        "--setup", action="store_true", help="Run the full automated setup script"
    )
    args = parser.parse_args()

    if args.migrate:
        migrate_db(initial=False)
        exit(0)
    else:
        run_setup()
        printc("[*] Database setup complete.")
