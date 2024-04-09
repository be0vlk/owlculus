"""
Contains the API endpoints for managing cases, including creating, updating, and deleting cases.
Includes functionality for managing case files and notes. See '/static/js/case.js' for the frontend.
"""

from flask import (
    Blueprint,
    jsonify,
    request,
    render_template,
    send_from_directory,
    current_app,
)
from flask.wrappers import Response
from flask_restful import Api, Resource, reqparse

from werkzeug.datastructures import FileStorage

from utils.db import db
from utils.models import Case, Client, Evidence, Note, User
from utils.helpers import (
    generate_case_number,
    setup_case_folder,
    rename_case_folder,
    delete_case_folder,
    upload_file,
    get_current_user,
)

from flask_jwt_extended import jwt_required
from api.auth import role_required, case_auth_required
from api.reports.reports import CaseReport

from sqlalchemy.exc import IntegrityError
import json
import os


cases_bp = Blueprint(
    "cases",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/cases",
)
api = Api(cases_bp)


class CaseList(Resource):
    @jwt_required()
    def get(self):
        current_user = get_current_user()
        include_archived = (
            request.args.get("include_archived", "false").lower() == "true"
        )

        if current_user.role == "admin":
            if include_archived:
                all_cases = Case.query.all()
            else:
                all_cases = Case.query.filter_by(archived=False).all()
        else:
            if include_archived:
                all_cases = current_user.authorized_cases
            else:
                all_cases = [
                    case for case in current_user.authorized_cases if not case.archived
                ]

        if "text/html" in request.headers.get("Accept", ""):
            html = render_template(
                "case_dashboard.html",
                cases=all_cases,
                clients=Client.query.all(),
                users=User.query.all(),
                current_user=current_user,
            )
            return Response(html, mimetype="text/html")
        else:
            return jsonify([case.serialize() for case in all_cases])

    @jwt_required()
    @role_required("admin")
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "case_type", required=True, help="Case type cannot be blank!"
        )
        parser.add_argument(
            "client_name", required=False, help="Client name must be valid."
        )
        parser.add_argument(
            "description", required=False, help="Optional short description."
        )
        parser.add_argument("assigned_users", action="append", help="List of user IDs.")
        args = parser.parse_args()

        client_id = None
        client_name = args.get("client_name")

        if client_name:
            client = Client.query.filter_by(name=client_name).first()
            if client is None:
                return {"message": "Client name does not exist."}, 404
            else:
                client_id = client.id

        case_number = generate_case_number()
        if case_number is None:
            return {"message": "Could not generate a valid case number."}, 500

        current_user = get_current_user()
        new_case = Case(
            case_number=case_number,
            case_type=args["case_type"],
            client_id=client_id,
            description=args["description"],
            created_by=current_user.username,
        )

        if args.get("assigned_users"):
            user_ids = [int(user_id) for user_id in args["assigned_users"]]
            assigned_users = User.query.filter(User.id.in_(user_ids)).all()
            new_case.authorized_users.extend(assigned_users)

        db.session.add(new_case)
        db.session.commit()

        # Load note categories from JSON file based on case type
        static_folder = current_app.static_folder
        if args["case_type"].lower() == "person":
            categories_path = os.path.join(static_folder, "person_notes.json")
        elif args["case_type"].lower() == "company":
            categories_path = os.path.join(static_folder, "company_notes.json")
        else:
            categories_path = os.path.join(static_folder, "note_categories.json")

        with open(categories_path) as f:
            note_categories = json.load(f)

        # Initialize notes for each category
        for category, fields in note_categories.items():
            if fields:
                note_data = {field["name"]: "" for field in fields}
            else:
                note_data = {}
            note = Note(case_id=new_case.id, category=category, data=note_data)
            db.session.add(note)

        try:
            setup_case_folder(
                case_number=new_case.case_number, case_type=args["case_type"]
            )
            db.session.commit()
            return {
                "message": f"Case created with ID: {new_case.id}",
                "case": new_case.serialize(),
            }, 201
        except Exception as e:
            db.session.rollback()
            return {
                "message": f"Error creating case and initializing notes: {str(e)}"
            }, 500


class CaseDetail(Resource):
    @jwt_required()
    @case_auth_required
    def get(self, case_id):
        case = Case.query.get_or_404(case_id)
        serialized_case = case.serialize()
        current_user = get_current_user()

        if "text/html" in request.headers.get("Accept", ""):
            notes = case.notes

            # Load note categories based on the case type
            static_folder = current_app.static_folder
            if case.case_type.lower() == "person":
                categories_path = os.path.join(static_folder, "person_notes.json")
            elif case.case_type.lower() == "company":
                categories_path = os.path.join(static_folder, "company_notes.json")
            else:
                categories_path = os.path.join(static_folder, "note_categories.json")

            with open(categories_path) as f:
                note_categories = json.load(f).keys()

            html = render_template(
                "case_detail.html",
                case=case,
                notes=notes,
                current_user=current_user,
                note_categories=note_categories,
            )
            return Response(html, mimetype="text/html")
        else:
            return jsonify(serialized_case)

    @jwt_required()
    @case_auth_required
    @role_required("investigator")
    def put(self, case_id):
        parser = reqparse.RequestParser()
        # Define the file argument; this is for documentation and structure, as reqparse doesn't handle files directly
        parser.add_argument(
            "file",
            type=FileStorage,
            location="files",
            required=True,
            help="File is required.",
        )
        parser.add_argument(
            "subfolder", location="form", required=False, help="Subfolder name."
        )

        args = parser.parse_args()
        file = args["file"]
        subfolder = args.get("subfolder")

        if file.filename == "":
            return {"message": "No selected file"}, 400

        case = Case.query.get_or_404(case_id)
        case_number = case.case_number

        if upload_file(
            file.filename, file.stream, case_number=case_number, subfolder=subfolder
        ):
            try:
                db.session.commit()
                return {"message": "File uploaded successfully"}, 200
            except Exception as e:
                db.session.rollback()
                return {"message": f"Failed to upload file: {str(e)}"}, 500
        else:
            return {"message": "Failed to upload file"}, 500

    @jwt_required()
    @role_required("investigator")
    @case_auth_required
    def patch(self, case_id):
        parser = reqparse.RequestParser()
        parser.add_argument("case_type", store_missing=False)
        parser.add_argument("case_number", store_missing=False)
        parser.add_argument("client_name", store_missing=False)
        parser.add_argument("description", store_missing=False)
        parser.add_argument("archived", type=bool, store_missing=False)
        args = parser.parse_args()

        # Directly accessing the JSON body for evidence
        json_data = request.get_json()
        evidence_data = json_data.get("evidence", [])

        case = Case.query.get_or_404(case_id)
        old_case_number = case.case_number
        new_case_number = args.get("case_number")
        if new_case_number:
            # Check if the new case number is already used by another case
            if Case.query.filter(
                Case.case_number == new_case_number, Case.id != case_id
            ).first():
                return {
                    "message": "Case number already in use. Please choose a different case number."
                }, 400

            case.case_number = new_case_number
            rename_case_folder(old_case_number, new_case_number)

        for key, value in args.items():
            if key != "evidence" and value is not None and hasattr(case, key):
                setattr(case, key, value)

        for evidence_item in evidence_data:
            evidence = Evidence.query.filter_by(value=evidence_item["value"]).first()
            if not evidence:
                evidence = Evidence(
                    evidence_type=evidence_item["evidence_type"],
                    value=evidence_item["value"],
                )
                db.session.add(evidence)
            if evidence not in case.evidence:
                case.evidence.append(evidence)

        db.session.add(case)
        try:
            db.session.commit()
            return {
                "message": "Case updated successfully",
                "case": case.serialize(),
            }, 200
        except IntegrityError:
            db.session.rollback()
            return {"message": "Case number must be unique. Update failed."}, 500
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error updating case: {str(e)}"}, 500

    @jwt_required()
    @role_required("admin")
    def delete(self, case_id):
        case = Case.query.get_or_404(case_id)
        case_number = case.case_number

        try:
            db.session.delete(case)
            db.session.commit()
            delete_case_folder(case_number)
            return {"message": "Case deleted successfully"}, 200
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error deleting case: {str(e)}"}, 500


class CaseFiles(Resource):
    @jwt_required()
    @case_auth_required
    def get(self, case_id):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "subpath", type=str, location="args", required=False, default=""
        )
        parser.add_argument("filename", type=str, location="args", required=False)
        args = parser.parse_args()

        subpath = args["subpath"]
        filename = args["filename"]

        case = Case.query.get_or_404(case_id)
        case_number = case.case_number
        base_case_folder_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], str(case_number)
        )

        # Ensure subpath is safely relative
        requested_path = os.path.normpath(os.path.join(base_case_folder_path, subpath))
        if not requested_path.startswith(base_case_folder_path):
            return {"message": "Access denied"}, 403

        if filename:
            # Attempt to serve the requested file
            file_path = os.path.join(requested_path, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(
                    os.path.dirname(file_path),
                    os.path.basename(file_path),
                    as_attachment=True,
                )
            else:
                return {"message": "File not found"}, 404
        else:
            # List directory contents
            if os.path.exists(requested_path):
                files = []
                for root, _, filenames in os.walk(requested_path):
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        relative_path = os.path.relpath(
                            file_path, base_case_folder_path
                        )
                        files.append(relative_path)
                return jsonify({"files": files})
            else:
                return {"message": "Directory not found"}, 404

    @jwt_required()
    @case_auth_required
    @role_required("investigator")
    def post(self, case_id):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "file",
            type=FileStorage,
            location="files",
            required=True,
            help="File is required.",
        )
        parser.add_argument("subfolder", type=str, location="form", required=False)
        args = parser.parse_args()

        file = args["file"]
        subfolder = args.get("subfolder")

        if file.filename == "":
            return {"message": "No selected file"}, 400

        case = Case.query.get_or_404(case_id)
        case_number = case.case_number

        if upload_file(
            file.filename, file.stream, case_number=case_number, subfolder=subfolder
        ):
            return {"message": "File uploaded successfully"}, 200
        else:
            return {"message": "Failed to upload file"}, 500


class CaseNotes(Resource):
    @jwt_required()
    @case_auth_required
    def get(self, case_id, note_id=None):
        if note_id:
            note = Note.query.filter_by(case_id=case_id, id=note_id).first_or_404()
            return jsonify(note.serialize())
        else:
            case = Case.query.get_or_404(case_id)
            return jsonify([note.serialize() for note in case.notes])

    @jwt_required()
    @case_auth_required
    @role_required("investigator")
    def post(self, case_id):
        json_data = request.get_json(force=True)
        category = json_data.get("category")
        new_data = json_data.get("data", {})

        if not category:
            return {"message": "Category cannot be blank!"}, 400

        note = Note.query.filter_by(case_id=case_id, category=category).first()

        if note:
            existing_data = note.data
            updated_data = {
                **existing_data,
                **new_data,
            }  # This merges the two dictionaries
            note.data = updated_data
            message = "Note updated successfully"
        else:
            note = Note(case_id=case_id, category=category, data=new_data)
            db.session.add(note)
            message = "Note added successfully"

        try:
            db.session.commit()
            return {"message": message}, 200 if note.id else 201
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error processing request: {str(e)}"}, 500

    @jwt_required()
    @case_auth_required
    @role_required("investigator")
    def patch(self, case_id, note_id=None):
        if note_id is None:
            return {"message": "Note ID is required for PATCH operation"}, 400

        json_data = request.get_json(force=True)
        new_data = json_data.get("data", {})

        # Fetch the specific note by both case_id and note_id
        note = Note.query.filter_by(case_id=case_id, id=note_id).first()
        if not note:
            return {"message": "Note not found"}, 404

        # Update the note's data with new data
        note.data = new_data

        try:
            db.session.commit()
            return {"message": "Note updated successfully"}, 200
        except Exception as e:
            db.session.rollback()
            return {"message": f"Error processing request: {str(e)}"}, 500


class AddUserToCase(Resource):
    @jwt_required()
    @role_required("admin")
    def post(self, case_id):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "user_id", type=int, required=True, help="User ID is required."
        )

        args = parser.parse_args()
        user_id = args["user_id"]
        case = Case.query.get(case_id)
        user = User.query.get(user_id)

        if case and user:
            if user not in case.authorized_users:
                case.authorized_users.append(user)
                db.session.commit()
                return {
                    "message": f"User {user.username} added to case {case.case_number}."
                }, 200
            else:
                return {
                    "message": f"User {user.username} is already authorized for case {case.case_number}."
                }, 400
        else:
            return {"message": "User or case not found."}, 404


# Add URL rules
api.add_resource(CaseList, "/")
api.add_resource(
    CaseNotes, "/<int:case_id>/notes", "/<int:case_id>/notes/<int:note_id>"
)
api.add_resource(CaseReport, "/<int:case_id>/report")
api.add_resource(AddUserToCase, "/<int:case_id>/add_user")
api.add_resource(CaseDetail, "/<int:case_id>", endpoint="case_detail")
api.add_resource(CaseFiles, "/<int:case_id>/files", endpoint="case_files")
