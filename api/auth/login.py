from werkzeug.security import check_password_hash
from flask import Blueprint, current_app, render_template, jsonify, make_response
from flask_restful import Api, Resource, reqparse
from utils.models import User
from flask_jwt_extended import create_access_token, set_access_cookies
from datetime import datetime
from utils.db import db

login_bp = Blueprint(
    "login",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/auth",
)
api = Api(login_bp)


class Login(Resource):
    def get(self):
        response = make_response(render_template("login.html"))
        response.headers["Content-Type"] = "text/html"
        return response

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("username", type=str, required=True)
        parser.add_argument("password", type=str, required=True)
        args = parser.parse_args()
        user = User.query.filter_by(username=args["username"]).first()

        if not user:
            return {"message": "User does not exist."}, 401
        elif not user.active:
            return {"message": "Account is not active. Please contact admin."}, 401
        elif check_password_hash(user.password, args["password"]):
            user.logged_in_at = datetime.utcnow()
            db.session.commit()
            access_token = create_access_token(
                identity=str(user.username), additional_claims={"role": user.role}
            )
            current_app.logger.debug("Returning access token")

            # Create the response object
            response = jsonify(
                {"message": "Login successful", "access_token": access_token}
            )
            set_access_cookies(response, access_token)
            return response
        else:
            return {"message": "Invalid username or password"}, 401


api.add_resource(Login, "")
