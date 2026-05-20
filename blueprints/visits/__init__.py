from flask import Blueprint
visits_bp = Blueprint("visits", __name__, url_prefix="/visits")
from . import routes
