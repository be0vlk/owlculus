import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from utils.db import db
from utils.helpers import printc

migrate = Migrate()


def create_app():
    app = Flask(__name__, static_folder="static")
    load_dotenv()

    app.config["SECRET_KEY"] = os.getenv("APP_SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=4)  # Adjust depending on your paranoia
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["MAX_CONTENT_LENGTH"] = (
        16 * 1000 * 1000
    )  # For forcing file uploads to be <=16 megabytes, can adjust

    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)
    CORS(app)
    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        return redirect("/login")

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return redirect("/login")

    # Import and register blueprints
    from api.cases.cases import cases_bp
    from api.clients.clients import clients_bp
    from api.auth.login import login_bp
    from api.admin.users import users_bp
    from api.tools.strixy import strixy_bp
    from api.tools.correlations import correlations_bp
    from api.tools.tool_runner import tool_runner_bp
    from api.reports.reports import reports_bp

    app.register_blueprint(cases_bp, url_prefix="/cases")
    app.register_blueprint(clients_bp, url_prefix="/clients")
    app.register_blueprint(login_bp, url_prefix="/login")
    app.register_blueprint(users_bp, url_prefix="/admin")
    app.register_blueprint(strixy_bp, url_prefix="/tools/strixy")
    app.register_blueprint(correlations_bp, url_prefix="/tools/correlations")
    app.register_blueprint(tool_runner_bp, url_prefix="/tools")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    @app.route("/")
    def index():
        return redirect("/cases/")

    return app

from utils import models

if __name__ == "__main__":
    migrations_folder = Path(__file__).parent / "migrations"
    main_app = create_app()
    if not migrations_folder.exists():
        printc("[*] Completing initial application setup")
        from utils.app_setup import run_setup
        run_setup(main_app)
        load_dotenv(override=True)

    main_app.run(debug=os.getenv("DEBUG"))
