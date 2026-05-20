from flask import Blueprint
telemedicine_bp = Blueprint("telemedicine", __name__, url_prefix="/telemedicine")
from . import routes  # noqa
