from flask import Blueprint
public_api_bp = Blueprint("public_api", __name__, url_prefix="/api/public")
from . import routes
