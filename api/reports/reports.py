"""
This module contains the API endpoint for generating basic reports for cases.
Use with caution for now, I haven't fully investigated the HTML -> PDF SSRF possibilities here yet.
"""

from flask import current_app, jsonify, Blueprint, request, Response, render_template
from flask_restful import Resource, Api
from flask_jwt_extended import jwt_required
from utils.models import Case, Note
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import os
from api.auth import case_auth_required


reports_bp = Blueprint(
    "reports",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/reports",
)
api = Api(reports_bp)


class CaseReport(Resource):
    """
    API endpoint for generating reports related to a specific case.

    The class provides a GET method that requires JWT authentication. The method generates a report for a case
    identified by its ID. The report includes details of the case and all notes associated with it.

    If the client accepts "text/html", the method returns the report as an HTML response. Otherwise, it generates
    an HTML report and a PDF report, saves them in the case's folder in the UPLOAD_FOLDER directory, and returns
    a JSON response indicating successful report generation.

    Methods:
        get(case_id: int): Generates and returns a report for a case identified by case_id.
    """

    @jwt_required()
    @case_auth_required
    def get(self, case_id):
        case = Case.query.get_or_404(case_id)
        notes = Note.query.filter_by(case_id=case_id).all()

        if "text/html" in request.headers.get("Accept", ""):
            html = render_template("reports.html", case=case, notes=notes)
            return Response(html, mimetype="text/html")
        else:
            env = Environment(loader=FileSystemLoader("templates/reports"), autoescape=True)
            template = env.get_template("reports.html")
            report_data = {"case": case, "notes": notes}
            html_report = template.render(report_data)

            # Save the HTML report to the case folder
            html_filename = f"{case.case_number}_report.html"
            html_file_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], case.case_number, "Reports", html_filename
            )
            with open(html_file_path, "w") as f:
                f.write(html_report)

            # Convert the HTML report to PDF and save it to the case folder
            pdf_filename = f"{case.case_number}_report.pdf"
            pdf_file_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], case.case_number, "Reports", pdf_filename
            )
            HTML(string=html_report).write_pdf(pdf_file_path)

            return jsonify({"message": "Report generated successfully"})


api.add_resource(CaseReport, "/<int:case_id>")
