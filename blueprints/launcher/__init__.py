from flask import Blueprint

launcher_bp = Blueprint("launcher", __name__)

from . import routes  # noqa: E402,F401
