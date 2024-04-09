"""
Contains functionality for running third-party tools directly from the app.
"""

import os
import shlex
import signal
import subprocess
from flask import Blueprint, render_template, Response, request, stream_with_context
from flask_restful import Resource, Api
from utils.helpers import upload_file
from utils.db import db
from utils.models import Case, Evidence, User
from flask_jwt_extended import jwt_required, get_jwt_identity

tool_runner_bp = Blueprint("tool_runner", __name__)
api = Api(tool_runner_bp)

current_directory = os.path.dirname(os.path.abspath(__file__))

AVAILABLE_TOOLS = {
    "maigret": "maigret {target}",
    "holehe": "holehe {target}",
    "phoneinfoga": "phoneinfoga scan -n '{target}'",
    "reddbaron": f"python3 {current_directory}/reddbaron.py {{target}}",
}

# Add the keys of the tools (from AVAILABLE_TOOLS ^) that analysts have access to.
# You will also need to adjust the templating logic in tools.html to properly display the tools.
# For example add 'analyst' to this array {% if current_user.role in ['admin', 'investigator'] %}.
ANALYST_TOOLS = []


def has_access_to_tool(user, tool):
    if user.role in ["admin", "investigator"]:
        return True
    elif user.role == "analyst":
        return tool in ANALYST_TOOLS
    return False


def run_tool(tool_name, target, case_number):
    if tool_name not in AVAILABLE_TOOLS:
        yield "Error: Tool not found"
        return

    safe_target = shlex.quote(target)
    safe_case_number = shlex.quote(case_number)
    safe_command_str = AVAILABLE_TOOLS[tool_name].format(
        target=safe_target, case_number=safe_case_number
    )
    command_list = shlex.split(safe_command_str)

    try:
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        for line in process.stdout:
            yield line
        return_code = process.wait()
        if return_code != 0:
            yield f"Error: Command exited with return code {return_code}"
    except subprocess.CalledProcessError as e:
        yield f"Error: {str(e)}"
    except GeneratorExit:
        if process:
            process.send_signal(signal.SIGINT)
            process.wait()
    except Exception as e:
        yield f"Error: An unexpected error occurred - {str(e)}"


def add_file_metadata_to_case(case_number, file_path, evidence_type):
    case = Case.query.filter_by(case_number=case_number).first_or_404()
    evidence = Evidence.query.filter_by(
        value=file_path, evidence_type=evidence_type
    ).first()
    if not evidence:
        evidence = Evidence(evidence_type=evidence_type, value=file_path)
        db.session.add(evidence)
    if evidence not in case.evidence:
        case.evidence.append(evidence)
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False


class ToolRunner(Resource):
    @jwt_required()
    def get(self):
        current_user = User.query.filter_by(username=get_jwt_identity()).first()
        if request.headers.get("Accept") == "text/event-stream":
            data = request.args
            tool = data.get("tool")
            target = data.get("target")
            case_number = data.get("case_number")

            if not has_access_to_tool(current_user, tool):
                return {"message": "Access denied"}, 403

            def generate():
                try:
                    for line in run_tool(tool, target, case_number):
                        yield f"data: {line}\n\n"
                except Exception as e:
                    yield f"data: Error: An unexpected error occurred - {str(e)}\n\n"
                finally:
                    yield "event: close\ndata: \n\n"

            headers = {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers=headers,
            )
        else:
            cases = (
                Case.query.all()
                if current_user.role == "admin"
                else current_user.authorized_cases
            )
            return Response(
                render_template("tools.html", cases=cases, current_user=current_user),
                mimetype="text/html",
            )

    @jwt_required()
    def post(self):
        current_user = User.query.filter_by(username=get_jwt_identity()).first()
        data = request.get_json()
        tool = data.get("tool")
        target = data.get("target")
        case_number = data.get("case_number")

        if not has_access_to_tool(current_user, tool):
            return {"message": "Access denied"}, 403

        def generate():
            try:
                output_lines = []
                for line in run_tool(
                    tool, target, case_number
                ):
                    yield f"data: {line}\n\n"
                    output_lines.append(line)

                output_content = "\n".join(output_lines)
                filename = f"{tool}_{target}.txt"
                if upload_file(filename, output_content, case_number):
                    file_path = f"{filename}"
                    if add_file_metadata_to_case(case_number, file_path, tool):
                        yield "data: File uploaded and evidence updated successfully\n\n"
                    else:
                        yield "data: Failed to update evidence\n\n"
                else:
                    yield "data: Failed to upload file\n\n"

            except Exception as e:
                yield f"data: Error: An unexpected error occurred - {str(e)}\n\n"
            finally:
                yield "event: close\ndata: \n\n"

        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers=headers,
        )


api.add_resource(ToolRunner, "")
