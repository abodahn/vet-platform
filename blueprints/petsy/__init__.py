from flask import Blueprint
petsy_bp = Blueprint("petsy", __name__, url_prefix="/petsy")
from . import routes  # noqa: E402, F401
