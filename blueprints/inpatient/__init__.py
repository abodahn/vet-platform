from flask import Blueprint
inpatient_bp = Blueprint("inpatient", __name__, url_prefix="/inpatient")
from blueprints.inpatient import routes  # noqa: F401, E402
