from flask import Blueprint
boarding_bp = Blueprint("boarding", __name__, url_prefix="/boarding")
from . import routes
