from flask import Blueprint
migration_bp = Blueprint('migration', __name__)
from . import routes
