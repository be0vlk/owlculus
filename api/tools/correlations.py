"""
This module contains functionality for finding correlations between cases based on given evidence.
When evidence is added to a case via the PATCH request in the API, it's assigned an ID in the database.
This tool will iterate all cases in the database and look to make those connections between evidence items.
It will also check for matching tool output filenames for tools that were run in the web app such as holehe.
"""

from flask import jsonify, Blueprint, current_app
from flask_restful import Resource, Api, reqparse
from flask_jwt_extended import jwt_required
import json

from utils.models import Case, Note, Evidence, case_evidence_association
from utils.db import db

correlations_bp = Blueprint(
    "correlations",
    __name__,
    static_folder="../../static",
    template_folder="../../templates/tools",
)
api = Api(correlations_bp)


def find_filename_correlations(case_id):
    """
    Finds correlations between cases based on matching filenames in evidence items.
    Args:
        case_id:

    Returns:
        dict: A dictionary with case numbers as keys and a list of correlated evidence data as values.

    """

    correlations = {}
    case_evidence = (
        db.session.query(Evidence)
        .join(case_evidence_association)
        .filter(case_evidence_association.c.case_id == case_id)
        .all()
    )

    for evidence in case_evidence:
        # Extract the filename from the evidence value
        filename = evidence.value.split("/")[-1]

        # Find cases with evidence items having the same filename
        similar_cases = (
            db.session.query(Case)
            .join(case_evidence_association)
            .join(Evidence)
            .filter(
                case_evidence_association.c.case_id != case_id,
                Evidence.value.like(f"%{filename}"),
            )
            .all()
        )

        for case in similar_cases:
            case_number = case.case_number
            print(f"Found matching case: {case_number}")
            if case_number not in correlations:
                correlations[case_number] = []
            correlations[case_number].append(
                {
                    "category": "Tool Output",
                    "key": "filename",
                    "value": filename,
                    "match_type": "Filename",
                }
            )

    return correlations


def find_note_correlations(case_id):
    """
    Finds correlations between notes of a given case and notes of other cases.

    Args:
        case_id (int): The ID of the case to find note correlations for.

    Returns:
        dict: A dictionary with case numbers as keys and a list of correlated note data as values.
    """
    correlations = {}
    case_notes = Note.query.filter_by(case_id=case_id).all()

    for note in case_notes:
        # Find notes in other cases with the same category
        similar_notes = Note.query.filter(
            Note.case_id != case_id, Note.category == note.category
        ).all()

        for similar_note in similar_notes:
            # Compare individual key-value pairs within the data JSON, skipping the "First Name" key
            for key, value in note.data.items():
                if key == "First Name":
                    continue

                if (
                        key in similar_note.data
                        and similar_note.data[key] == value
                        and value.strip()
                ):
                    case_number = Case.query.get(similar_note.case_id).case_number
                    if case_number not in correlations:
                        correlations[case_number] = []
                    correlations[case_number].append(
                        {
                            "category": note.category,
                            "key": key,
                            "value": value,
                            "match_type": "Note",
                        }
                    )

    return correlations


def find_correlations(input_case=None, all_cases=False):
    """
    Finds correlations between cases based on given evidence. If a specific case is provided,
    it finds correlations for that case. If all_cases is set to True, it finds correlations
    between all cases.

    Args:
        input_case (str, optional): The case number to find correlations for.
        all_cases (bool, optional): Whether to find correlations between all cases.

    Returns: dict: Case numbers as keys and a dict of correlated case numbers and evidence as values.
    """

    correlations = {}

    if all_cases:
        cases = Case.query.all()
        for case in cases:
            case_correlations = find_note_correlations(case.id)
            filename_correlations = find_filename_correlations(case.id)

            # Merge note and filename correlations
            for case_number, matches in filename_correlations.items():
                if case_number not in case_correlations:
                    case_correlations[case_number] = []
                case_correlations[case_number].extend(matches)

            if case_correlations:
                correlations[case.case_number] = case_correlations
    elif input_case:
        case = Case.query.filter_by(case_number=input_case).first()
        if case:
            case_correlations = find_note_correlations(case.id)
            filename_correlations = find_filename_correlations(case.id)

            # Merge note and filename correlations
            for case_number, matches in filename_correlations.items():
                if case_number not in case_correlations:
                    case_correlations[case_number] = []
                case_correlations[case_number].extend(matches)

            if case_correlations:
                correlations[case.case_number] = case_correlations

    return correlations


def save_correlations(base_path, input_case, correlations):
    """
    Save correlations for a specified case or all cases to JSON files.

    Args:
        base_path (str): The base directory for storage.
        input_case (str): The case number to save correlations for (if provided).
        correlations (dict): The correlations dictionary.
    """
    if input_case:
        cases = [input_case]
    else:
        cases = correlations.keys()

    for case_number in cases:
        case_correlations = correlations.get(case_number, {})
        grouped_correlations = {}

        for correlated_case, correlated_evidence in case_correlations.items():
            if correlated_case not in grouped_correlations:
                grouped_correlations[correlated_case] = []

            for evidence in correlated_evidence:
                grouped_correlations[correlated_case].append(
                    {
                        "Category": evidence["category"],
                        "Key": evidence["key"],
                        "Value": evidence["value"],
                        "Match Type": evidence["match_type"],
                    }
                )

        correlation_info = []
        for correlated_case, evidence_list in grouped_correlations.items():
            correlation_info.append(
                {"Matched Case Number": correlated_case, "Evidence": evidence_list}
            )

        if correlation_info:  # Write only if there are correlations to report
            output_json_path = f"{base_path}/{case_number}/correlations.json"
            with open(output_json_path, "w") as file:
                json.dump(correlation_info, file, indent=4)


class Correlations(Resource):
    """
    The API endpoint for running the correlations tool.
    """

    @jwt_required()
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("case_number", type=str, required=False)
        parser.add_argument("all_cases", type=bool, default=False)
        args = parser.parse_args()

        case_number = args.get("case_number")
        all_cases = args.get("all_cases")

        correlations = find_correlations(case_number, all_cases)
        save_correlations(
            current_app.config["UPLOAD_FOLDER"], case_number, correlations
        )

        return jsonify(correlations)


api.add_resource(Correlations, "")
