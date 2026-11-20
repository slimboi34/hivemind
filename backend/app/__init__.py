"""
Hivemind Backend - Flask application factory
"""

import os
import warnings

# Silence multiprocessing resource_tracker warnings (raised by third-party libraries such as transformers).
# This must run before every other import.
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # JSON encoding: emit non-ASCII text as-is rather than as \uXXXX escapes.
    # Flask >= 2.3 uses app.json.ensure_ascii; older versions use the JSON_AS_ASCII setting.
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Logging
    logger = setup_logger('hivemind')
    
    # Print the startup banner only in the reloader child process (otherwise debug mode prints it twice)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Hivemind Backend starting...")
        logger.info("=" * 50)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register the simulation-process cleanup hook (so every simulation process is stopped when the server shuts down)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Registered the simulation-process cleanup hook")
    
    # Request-logging middleware
    @app.before_request
    def log_request():
        logger = get_logger('hivemind.request')
        logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Request body: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('hivemind.request')
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp, godseye_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(godseye_bp, url_prefix='/api/godseye')
    
    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'Hivemind Backend'}

    # Public-site limits, AGPL source download and the owner's data import
    from . import public_mode
    public_mode.register(app)

    # Serve the built frontend when there is one (single-port deployments such as Railway)
    static_dir = os.environ.get('HIVEMIND_STATIC_DIR', '')
    if static_dir and os.path.isfile(os.path.join(static_dir, 'index.html')):
        from flask import send_from_directory, abort

        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def frontend(path):
            if path.startswith('api/'):
                abort(404)
            full = os.path.join(static_dir, path)
            if path and os.path.isfile(full):
                return send_from_directory(static_dir, path, max_age=31536000 if path.startswith('assets/') else 0)
            return send_from_directory(static_dir, 'index.html', max_age=0)
    
    if should_log_startup:
        logger.info("Hivemind Backend started")
    
    return app

