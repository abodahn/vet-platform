from flask import Blueprint

imaging_bp = Blueprint("imaging", __name__, url_prefix="/imaging")

from . import routes
