"""
The auth package contains the authentication and authorization logic for the API.
See login.py for the authentication logic specifically.
"""

from flask_jwt_extended import get_jwt, get_jwt_identity
from utils.models import User, Case
from functools import wraps

ROLE_HIERARCHY = {"analyst": 1, "investigator": 2, "admin": 3}


# The role_required decorator is used to restrict access to certain routes based on the role of the user.
# Roles and their names are defined in utils.models.User
def role_required(role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get("role")
            if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY.get(role):
                return {"message": "Access denied"}, 403
            else:
                return fn(*args, **kwargs)

        return wrapper

    return decorator


# The case_auth_required decorator is used to restrict access to certain routes.
# It checks if the user is authorized to access the case with the given case_id.
def case_auth_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        case_id = kwargs.get('case_id')
        if case_id:
            current_user = User.query.filter_by(username=get_jwt_identity()).first()
            case = Case.query.get(case_id)
            if current_user.role != "admin" and case not in current_user.authorized_cases:
                return {"message": "You are not authorized to access this case."}, 403
        return func(*args, **kwargs)
    return decorated_function
