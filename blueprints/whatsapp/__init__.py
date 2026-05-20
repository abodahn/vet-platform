from flask import Blueprint
whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/whatsapp")
from . import routes
