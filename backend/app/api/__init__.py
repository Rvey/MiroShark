"""
API Routes Module
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
marketing_strategy_bp = Blueprint('marketing_strategy', __name__)
templates_bp = Blueprint('templates', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import marketing_strategy  # noqa: E402, F401
from . import templates  # noqa: E402, F401

