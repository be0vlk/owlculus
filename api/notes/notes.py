from flask import jsonify, Blueprint, render_template, Response, request
from flask_restful import Resource, reqparse, Api

notes_bp = Blueprint("notes", __name__, static_folder="../../static", template_folder="../../templates/notes")
api = Api(notes_bp)


class NotesList(Resource):
    """
    This class handles HTTP GET and POST requests at the root '/notes' endpoint.
    """

    def get(self):
        if "text/html" in request.headers.get("Accept", ""):
            html = render_template("notes.html")
            return Response(html, mimetype="text/html")
        else:
            return jsonify({"message": "Not fully implemented"})

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("title", type=str, required=True, help="Title is required")
        parser.add_argument(
            "content", type=str, required=True, help="Content is required"
        )
        args = parser.parse_args()
        return jsonify(args)


api.add_resource(NotesList, "")
