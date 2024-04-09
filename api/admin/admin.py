from flask import Blueprint, render_template


dashboard = Blueprint(
    "dashboard", __name__, static_folder="static", template_folder="templates/admin"
)


@dashboard.route("/")
@dashboard.route("/dashboard")
def index():
    return render_template("admin/admin_dashboard.html")
