from flask import Blueprint

ai_bp = Blueprint("ai_assistant", __name__, url_prefix="/ai")

from . import routes
