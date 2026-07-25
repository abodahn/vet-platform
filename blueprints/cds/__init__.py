from flask import Blueprint

cds_bp = Blueprint("cds", __name__, url_prefix="/cds")

from . import routes  # noqa: E402,F401
