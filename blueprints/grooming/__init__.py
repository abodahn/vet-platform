from flask import Blueprint
grooming_bp = Blueprint("grooming", __name__, url_prefix="/grooming")
from . import routes
