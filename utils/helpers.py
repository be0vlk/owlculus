from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app, abort
from utils.models import Case, User
import shutil
import re
import builtins
from colorama import init, Fore
import os
import secrets
from flask_jwt_extended import get_jwt_identity

# Initialize colorama
init(autoreset=True)

# Used in the printc and colorize functions
WHITE = Fore.WHITE
CYAN = Fore.CYAN
MAGENTA = Fore.MAGENTA
GREEN = Fore.GREEN
YELLOW = Fore.YELLOW

# These are used to define the on-disk directory layouts for different case types
COMMON_FOLDERS = ["Artifacts", "Reports"]
SOCIAL_MEDIA_FOLDERS = ["Facebook", "Twitter", "Instagram"]

# The filesystem path where cases are stored when created and what file extensions are allowed
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER")
ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "md",
    "html",
    "csv",
    "json",
}


def validate_patch(resource, args):
    """
    Iterate through args and update only the provided fields if they are not None or empty strings,
    and if the resource has an attribute with the same name.

    Args:
        resource: The resource object to be updated.
        args (dict): A dictionary containing the fields to update along with their new values.

    Raises:
        HTTPException: If all values in args are empty strings, it aborts with a 400 status code.
    """

    updated = False

    for key, value in args.items():
        if value not in [None, ""] and hasattr(resource, key):
            setattr(resource, key, value)
            updated = True

    if not updated:
        abort(400, description="Values cannot be empty strings")


def validate_format(value):
    patterns = {
        "email": r"^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$"
        # Add more patterns here
    }
    key = "email"
    if key in patterns:
        pattern = re.compile(patterns[key])
        if not pattern.match(value):
            return False
    return True


def generate_password():
    """
    Generates a random, secure password.
    """

    password = secrets.token_urlsafe(18)
    return password


def get_current_user():
    """
    Returns the current user's id.
    """

    return User.query.filter_by(username=get_jwt_identity()).first()


def generate_case_number():
    """
    Generates a unique case number based on the current date and existing case numbers.
    """

    try:
        date = datetime.now().strftime("%y%m")
        for i in range(1, 100):
            case_number = f"{date}-{str(i).zfill(2)}"
            if not Case.query.filter_by(case_number=case_number).first():
                return case_number
        current_app.logger.error("No available case numbers")
        return None
    except Exception as e:
        current_app.logger.error(f"Error generating case number: {e}")
        return None


def setup_case_folder(case_number=None, case_type=None):
    """
    Sets up a new case folder with the given name and type, then populates it with pre-made JSON templates.
    """

    current_app.logger.debug("Setting up case folder.")
    base_path = Path(current_app.config["UPLOAD_FOLDER"])
    case_folder_path = base_path / secure_filename(case_number)
    templates_path = Path(current_app.root_path) / "notetaking_templates"

    if not case_folder_path.exists():
        current_app.logger.debug("Creating case folder.")
        case_folder_path.mkdir(parents=True)

    folders = COMMON_FOLDERS.copy()
    if case_type == "Company":
        current_app.logger.debug("Adding company-specific folders.")
        c_suite_roles = ["CEO", "CTO", "CFO", "CMO", "COO"]
        c_suite_folders = [f"Executives/{role}" for role in c_suite_roles]
        folders.extend(["Domains", "Executives", "Network"] + c_suite_folders)

    for folder in folders:
        current_app.logger.debug(f"Creating folder: {folder}")
        (case_folder_path / folder).mkdir(exist_ok=True)

    for folder in SOCIAL_MEDIA_FOLDERS:
        current_app.logger.debug(f"Creating social media folder: {folder}")
        (case_folder_path / "Social_Media" / folder).mkdir(parents=True, exist_ok=True)

    template_to_folder = {
        "Notes": "",
        "SOCMINT": "Social_Media",
        "Associates": "Associates",
        # Extend this dictionary based on your template needs
    }

    for template_file in templates_path.glob("*.md"):
        template_name = template_file.stem
        current_app.logger.debug(f"Processing template: {template_name}")
        target_folder = template_to_folder.get(template_name, "")
        target_path = case_folder_path / target_folder / template_file.name

        # Automatically adds some basic case information to the note-taking template
        if template_name == "Notes":
            current_app.logger.debug("Initializing note template.")
            with open(template_file, "r", encoding="utf-8") as f:
                content = f.read()
            content = content.format(
                case_number=case_number,
                case_type=case_type,
                date=datetime.now().strftime("%m-%d-%Y"),
            )
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

    current_app.logger.info(f"Case folder setup complete for: {case_number}")


def rename_case_folder(old_case_number, new_case_number):
    """
    Renames the case folder from the old case number to the new case number.
    """

    base_path = Path(current_app.config["UPLOAD_FOLDER"])
    old_case_folder_path = base_path / secure_filename(old_case_number)
    new_case_folder_path = base_path / secure_filename(new_case_number)

    if old_case_folder_path.exists() and old_case_number != new_case_number:
        current_app.logger.debug(
            f"Renaming case folder from {old_case_number} to {new_case_number}."
        )
        shutil.move(str(old_case_folder_path), str(new_case_folder_path))
        current_app.logger.info(
            f"Case folder renamed successfully to: {new_case_number}"
        )
    else:
        current_app.logger.debug(
            "Old case folder does not exist or case number has not changed."
        )


def delete_case_folder(case_number=None):
    """
    Deletes a case folder with the given case number.
    """

    current_app.logger.debug("Deleting case folder.")

    base_path = Path(current_app.config["UPLOAD_FOLDER"])
    case_folder_path = base_path / secure_filename(case_number)

    if case_folder_path.exists():
        current_app.logger.debug("Removing case folder.")
        shutil.rmtree(case_folder_path)

    current_app.logger.info(f"Case folder deleted: {case_number}")


def upload_file(filename, file_stream, case_number=None, subfolder=None):
    # Check file extension
    if "." in filename and filename.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
        return False

    upload_path = Path(UPLOAD_FOLDER)
    if case_number:
        upload_path /= case_number
        if subfolder:
            upload_path /= subfolder
        os.makedirs(upload_path, exist_ok=True)

    upload_path /= filename

    try:
        if isinstance(file_stream, str):
            with open(upload_path, "w") as f:
                f.write(file_stream)
        else:
            with open(upload_path, "wb") as f:
                f.write(file_stream.read())
        return True
    except Exception as e:
        print(f"Failed to upload file: {e}")
        return False


def colorize(message):
    """
    Colorizes a message by replacing specific markers with color codes.

    Args:
        message (str): The message to be colorized.

    Returns:
        str: The colorized message.

    """

    colorized_message = message
    colorized_message = re.sub(r"\[\*]", f"{CYAN}[*]{WHITE}", colorized_message)
    colorized_message = re.sub(r"\[!]", f"{YELLOW}[!]{WHITE}", colorized_message)
    colorized_message = re.sub(r"\[-]", f"{MAGENTA}[-]{WHITE}", colorized_message)
    return colorized_message


def printc(*args, **kwargs):
    """
    Colorized version of the print function.

    This function takes the same arguments as the built-in print function and prints the colorized output.

    Args:
        *args: The positional arguments to be printed.
        **kwargs: The keyword arguments to be passed to the built-in print function.

    """
    builtins.print(*(colorize(arg) for arg in args), **kwargs)
