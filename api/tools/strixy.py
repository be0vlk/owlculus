import os
import openai
import werkzeug
from flask import Blueprint, jsonify
from flask_restful import Resource, Api, reqparse
from openai import OpenAI
from time import sleep
from flask_jwt_extended import jwt_required
from api.auth import role_required

strixy_bp = Blueprint("strixy", __name__)
api = Api(strixy_bp)

client = OpenAI()
thread = None


def query_gpt(query, new_thread=False, file_ids=None):
    """
    Queries GPT with the provided query, optionally ends the current thread to start a new one,
    and optionally passes file IDs to the thread.

    Args:
        query (str): The query to send to GPT.
        new_thread (bool, optional): Whether to end the current thread and start a new one. Defaults to False.
        file_ids (list, optional): A list of file IDs to pass to the thread. Defaults to None.

    Returns:
        str: The response from GPT.
    """
    global thread

    try:
        assistant = client.beta.assistants.retrieve(os.getenv("GPT_ASSISTANT_ID"))
    except openai.NotFoundError:
        return "No GPT Assistant found matching the provided ID."

    # End the current thread and start a new one if requested
    if new_thread or not thread:
        thread_data = {"messages": []}
        if file_ids:
            # Convert file_ids to a list if it's a single string
            if isinstance(file_ids, str):
                file_ids = [file_ids]
            # Limit the number of file IDs to a maximum of 10
            file_ids = file_ids[:10]
            thread_data["messages"].append(
                {"role": "user", "file_ids": file_ids, "content": query}
            )
        else:
            thread_data["messages"].append({"role": "user", "content": query})
        thread = client.beta.threads.create(**thread_data)

    message_data = {"thread_id": thread.id, "role": "user", "content": f"{query}"}
    if file_ids:
        message_data["file_ids"] = file_ids
    message = client.beta.threads.messages.create(**message_data)
    run = client.beta.threads.runs.create(
        thread_id=thread.id, assistant_id=assistant.id
    )

    while run.status != "completed":
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        sleep(1)

    all_messages = client.beta.threads.messages.list(thread_id=thread.id)

    return all_messages.data[0].content[0].text.value, message.thread_id


class Strixy(Resource):

    @jwt_required()
    @role_required("admin")
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "query", type=str, help="Query parameter is required", required=True
        )
        parser.add_argument(
            "new_thread",
            type=bool,
            help="Specify true to end the current thread and start a new one.",
            required=False,
            default=False,
        )
        parser.add_argument(
            "file_ids",
            type=list,
            help="A list of file IDs to pass to the thread.",
            required=False,
            location="json",
        )
        args = parser.parse_args()
        query = args.get("query")
        new_thread = args.get("new_thread")
        file_ids = args.get("file_ids")
        if file_ids and not isinstance(file_ids, list):
            file_ids = [file_ids]
        response = query_gpt(query, new_thread=new_thread, file_ids=file_ids)
        return jsonify({"response": response[0], "thread_id": response[1]})


class FileUpload(Resource):

    @jwt_required()
    @role_required("admin")
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            "file",
            type=werkzeug.datastructures.FileStorage,
            location="files",
            required=True,
        )
        args = parser.parse_args()
        file = args.get("file")

        try:
            file_content = file.read()
            file_name = file.filename
            response = client.files.create(file=(file_name, file_content), purpose="assistants")
            file_id = response.id
            return jsonify({"file_id": file_id})
        except openai.OpenAIError as e:
            return jsonify({"error": str(e)}), 400


class FileList(Resource):
    @jwt_required()
    @role_required("admin")
    def get(self):
        files = client.files.list()
        file_list = [
            {
                "id": file.id,
                "filename": file.filename,
                "purpose": file.purpose,
                "created_at": file.created_at,
            }
            for file in files.data
        ]
        return jsonify(file_list)


api.add_resource(Strixy, "")
api.add_resource(FileUpload, "/upload")
api.add_resource(FileList, "/files")
