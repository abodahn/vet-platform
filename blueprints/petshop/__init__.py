from flask import Blueprint
petshop_bp = Blueprint('petshop', __name__)
from . import routes
