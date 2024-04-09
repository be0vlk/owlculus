from flask import jsonify, Blueprint, abort, render_template, request, Response
from flask_restful import Api, Resource, reqparse
from utils.db import db
from utils.models import Client
from utils.helpers import validate_patch, validate_format, get_current_user
from flask_jwt_extended import jwt_required
from api.auth import role_required
from datetime import datetime

clients_bp = Blueprint(
    "clients",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/clients",
)
api = Api(clients_bp)


class ClientList(Resource):
    @jwt_required()
    @role_required("investigator")
    def get(self):
        all_clients = Client.query.all()

        # Is it a browser or direct API call
        if "text/html" in request.headers.get("Accept", ""):
            html = render_template("client_dashboard.html", clients=all_clients)
            return Response(html, mimetype="text/html")
        else:
            return jsonify([client.serialize() for client in all_clients])

    @jwt_required()
    @role_required("investigator")
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("name", required=True, help="Name cannot be blank!")
        parser.add_argument("email", store_missing=False)
        parser.add_argument("phone", store_missing=False)
        args = parser.parse_args()

        # Check if client already exists
        existing_client = Client.query.filter_by(name=args["name"]).first()
        if existing_client:
            abort(
                400,
                description=f"Client with name {args['name']} already exists",
            )

        client = Client(
            name=args["name"],
            email=args.get("email", None),
            phone=args.get("phone", None),
        )
        try:
            db.session.add(client)
            db.session.commit()
            return {
                "message": "Client added successfully",
                "client": client.serialize(),
            }, 201
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error adding client: {str(e)}"}, 500


class ClientDetail(Resource):

    @jwt_required()
    @role_required("investigator")
    def get(self, client_id):
        client = Client.query.get_or_404(client_id)
        current_user = get_current_user()

        # Is it a browser or direct API call
        if "text/html" in request.headers.get("Accept", ""):
            html = render_template("client_detail.html", client=client, current_user=current_user)
            return Response(html, mimetype="text/html")
        else:
            return jsonify(client.serialize())

    @jwt_required()
    @role_required("investigator")
    def patch(self, client_id):
        parser = reqparse.RequestParser()
        parser.add_argument("name", store_missing=False)
        parser.add_argument("email", store_missing=False)
        parser.add_argument("phone", store_missing=False)
        args = parser.parse_args()

        client = Client.query.get_or_404(client_id)
        if args.get("email"):
            if not validate_format(args.get("email")):
                abort(400, description="Invalid email")

        validate_patch(client, args)

        try:
            client.updated_at = datetime.utcnow()
            db.session.commit()
            return {
                "message": "Client updated successfully",
                "client": client.serialize(),
            }, 200
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error updating client: {str(e)}"}, 500

    @jwt_required()
    @role_required("admin")
    def delete(self, client_id):
        client = Client.query.get_or_404(client_id)

        # Check if client has any cases associated
        if client.cases:
            case_numbers = [case.case_number for case in client.cases]
            return {
                "message": "Cannot delete client because there are cases associated with them",
                "associated_cases": case_numbers,
            }, 409

        db.session.delete(client)
        try:
            db.session.commit()
            return {"message": "Client deleted successfully"}, 200
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error deleting client: {str(e)}"}, 500


api.add_resource(ClientList, "/")
api.add_resource(ClientDetail, "/<int:client_id>")

if __name__ == "__main__":
    pass
