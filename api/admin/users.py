from flask import Blueprint, jsonify, request, Response, render_template
from flask_restful import Api, Resource, reqparse
from utils.models import User
from flask_jwt_extended import jwt_required
from api.auth import role_required
from werkzeug.security import generate_password_hash
from utils.db import db
from utils.helpers import validate_format, generate_password
from datetime import datetime

users_bp = Blueprint(
    "users",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/admin",
)
api = Api(users_bp)


class UsersList(Resource):
    """
    This class handles HTTP GET and POST requests at the root '/admin/users' endpoint.
    """

    @jwt_required()
    @role_required("admin")
    def get(self):
        all_users = User.query.all()
        if "text/html" in request.headers.get("Accept", ""):
            html = render_template("admin_dashboard.html", users=all_users)
            return Response(html, mimetype="text/html")
        else:
            return jsonify([user.serialize() for user in all_users])

    @jwt_required()
    @role_required("admin")
    def post(self):

        parser = reqparse.RequestParser()
        parser.add_argument(
            "username", type=str, required=True, help="Username is required"
        )
        parser.add_argument(
            "password", type=str, required=False, help="Password is required"
        )
        parser.add_argument("email", type=str, required=True, help="Email is required")
        parser.add_argument("role", type=str, required=True, help="Role is required")
        args = parser.parse_args()

        if validate_format(args["email"]):
            existing_email = User.query.filter_by(email=args["email"]).first()
            existing_user = User.query.filter_by(username=args["username"]).first()
            if existing_user or existing_email:
                return {"message": "User already exists"}, 400
        else:
            return {"message": "Email format is invalid"}, 400

        if not args["password"]:
            args["password"] = generate_password()
        hashed_password = generate_password_hash(args["password"])

        new_user = User(
            username=args["username"],
            password=hashed_password,
            email=args["email"],
            role=args["role"],
        )

        db.session.add(new_user)
        db.session.commit()
        return {
            "message": "User created successfully with password: " + args["password"]
        }, 201


class UsersDetail(Resource):
    """
    This class handles the HTTP GET, PATCH, and DELETE methods for individual users.
    """

    @jwt_required()
    @role_required("admin")
    def get(self, user_id):
        user = User.query.get(user_id)
        if user:
            return jsonify(user.serialize())
        else:
            return {"message": "User not found"}, 404

    @jwt_required()
    @role_required("admin")
    def patch(self, user_id):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "username", type=str, required=False, help="Change username"
        )
        parser.add_argument(
            "password", type=str, required=False, help="Change password"
        )
        parser.add_argument("email", type=str, required=False, help="Change email")
        parser.add_argument(
            "role", type=str, required=False, help="Change assigned role"
        )
        parser.add_argument(
            "active", type=bool, required=False, help="Change the user's active status"
        )

        args = parser.parse_args()
        user = User.query.get_or_404(user_id)
        password_updated = False

        for key, value in args.items():
            if value is not None and value != "":
                if key == "password":
                    hashed_password = generate_password_hash(value)
                    user.password = hashed_password
                    password_updated = True
                elif hasattr(user, key):
                    setattr(user, key, value)

        try:
            user.updated_at = datetime.utcnow()
            if password_updated:
                user.last_password_change = datetime.utcnow()
            db.session.commit()
            return {
                "message": "User updated successfully",
                "user": user.serialize(),
            }, 200
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error updating user: {str(e)}"}, 500

    @jwt_required()
    @role_required("admin")
    def delete(self, user_id):
        from flask_jwt_extended import get_jwt_identity

        current_username = get_jwt_identity()
        user = User.query.get(user_id)

        if user:
            if user.username == current_username:
                return {"message": "You cannot delete your own account"}, 400
            db.session.refresh(user)
            db.session.delete(user)
            db.session.commit()
            return {"message": f"User {user.username} deleted successfully"}
        else:
            return {"message": "User not found"}, 404


api.add_resource(UsersList, "/users")
api.add_resource(UsersDetail, "/users/<int:user_id>")
