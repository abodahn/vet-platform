from flask import Blueprint
procurement_bp = Blueprint("procurement", __name__, url_prefix="/procurement")
from . import routes
