"""
This module contains the API endpoints for managing users.
"""

from datetime import datetime, timedelta
import os

from flask import Blueprint, jsonify, make_response, render_template, request, Response
from flask_jwt_extended import jwt_required
from flask_restful import Api, Resource, reqparse
from werkzeug.security import generate_password_hash

from api.auth import role_required
from utils.db import db
from utils.helpers import generate_password, validate_format
from utils.models import Invitation, User


users_bp = Blueprint(
    "users",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/admin",
)
api = Api(users_bp)


class UsersList(Resource):
    """
    API endpoint for managing users in the system.

    It provides two HTTP methods:
    - GET: Retrieves a list of all users. If the request's Accept header includes "text/html",
      it returns an HTML response with a rendered template. Otherwise, it returns a JSON response
      with a list of serialized user objects.
    - POST: Creates a new user. The request must include the username, email, and role.
      If a password is not provided, a random one is generated. If a user with the provided
      username or email already exists, the request fails. Otherwise, a new user is created
      and a success message is returned along with the generated password.
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
    API endpoint for managing individual users in the system.

    It provides three HTTP methods:
    - GET: Retrieves the details of a specific user identified by user_id. If the user exists,
      it returns a JSON response with the serialized user object. Otherwise, it returns a message
      indicating that the user was not found.
    - PATCH: Updates the details of a specific user identified by user_id. The request can include
      changes to the username, password, email, role, and active status. If the user exists and the
      update is successful, it returns a success message along with the updated user object.
      Otherwise, it returns an error message.
    - DELETE: Deletes a specific user identified by user_id. If the user exists and the deletion is
      successful, it returns a success message. Otherwise, it returns a message indicating that the
      user was not found.
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


class InvitationsList(Resource):
    """
    API endpoint for creating one-time registration invites.

    It provides one HTTP method:
    - POST: Creates a new invitation. The request must include the role. If the role is provided,
      a new invitation is created with a generated token and an expiration date set to 2 days from
      the current date. The response includes a success message and the invitation link.
    """

    @jwt_required()
    @role_required("admin")
    def post(self):
        data = request.get_json()
        role = data.get("role")

        if not role:
            return {"message": "Role is required"}, 400

        token = generate_password()
        expires_at = datetime.utcnow() + timedelta(days=2)

        new_invitation = Invitation(token=token, role=role, expires_at=expires_at)

        db.session.add(new_invitation)
        db.session.commit()

        domain = os.getenv("DOMAIN")
        invite_link = f"{domain}/admin/register?token={token}"
        return {
            "message": "Invitation created successfully",
            "invite_link": invite_link,
        }, 201


class UserRegistration(Resource):
    """
    API endpoint for user registration.

    It provides two HTTP methods:
    - GET: Retrieves the registration page for a specific invitation identified by a token. If the
      token is valid and the invitation is not used or expired, it returns the registration page.
      Otherwise, it returns an error message.
    - POST: Registers a new user. The request must include the token, username, password, and email.
      If all required fields are provided and the token is valid, a new user is created and the
      invitation is marked as used. If the user registration is successful, it returns a success
      message. Otherwise, it returns an error message.
    """

    def get(self):
        token = request.args.get("token")
        if not token:
            return "Invalid invitation link", 400

        invitation = Invitation.query.filter_by(token=token).first()
        if (
            not invitation
            or invitation.used
            or invitation.expires_at < datetime.utcnow()
        ):
            return "Invalid or expired invitation", 400

        return make_response(render_template("register.html", token=token))

    def post(self):
        data = request.get_json()
        token = data.get("token")
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")

        if not token or not username or not password or not email:
            return {"message": "Missing required fields"}, 400

        invitation = Invitation.query.filter_by(token=token).first()
        if (
            not invitation
            or invitation.used
            or invitation.expires_at < datetime.utcnow()
        ):
            return {"message": "Invalid or expired invitation"}, 400

        existing_email = User.query.filter_by(email=email).first()
        existing_user = User.query.filter_by(username=username).first()
        if existing_user or existing_email:
            return {"message": "User already exists"}, 400

        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_password,
            email=email,
            role=invitation.role,
        )

        invitation.used = True
        db.session.add(new_user)
        db.session.commit()
        return {"message": "User registered successfully"}, 201


api.add_resource(InvitationsList, "/invitations")
api.add_resource(UserRegistration, "/register")
api.add_resource(UsersList, "/users")
api.add_resource(UsersDetail, "/users/<int:user_id>")
