"""
Hivemind Backend entry point
"""

import os
import sys

# Avoid garbled non-ASCII output in the Windows console: switch to UTF-8 before any other import
if sys.platform == 'win32':
    # Make Python use UTF-8 for its standard streams
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # Reconfigure stdout/stderr as UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Put the backend directory (this file's folder) on the import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """Entry point."""
    # Validate the configuration
    errors = Config.validate()
    if errors:
        print("Configuration error:")
        for err in errors:
            print(f"  - {err}")
        print("\nCheck the settings in your .env file")
        sys.exit(1)
    
    # Create the app
    app = create_app()
    
    # Read the run settings
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT') or os.environ.get('PORT') or 5001)
    debug = Config.DEBUG
    
    # Start the server
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()

