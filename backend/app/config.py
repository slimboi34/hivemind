"""
Configuration
Loads every setting from the .env file in the project root.
"""

import os
from dotenv import load_dotenv

# Load the .env file in the project root
# Path: Hivemind/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # No .env in the project root: fall back to the process environment (used in production)
    load_dotenv(override=True)


class Config:
    """Flask configuration."""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'hivemind-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # JSON: disable ASCII escaping so non-ASCII text is returned as-is
    JSON_AS_ASCII = False
    
    # LLM (always called through the OpenAI-compatible API)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # God's Eye View (optional live situational data for seed documents)
    GODSEYE_URL = os.environ.get('GODSEYE_URL', 'http://localhost:4173')
    
    # File uploads
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # Text processing
    DEFAULT_CHUNK_SIZE = 500  # default chunk size
    DEFAULT_CHUNK_OVERLAP = 50  # default chunk overlap
    
    # OASIS simulation
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    # After the last round, how long to wait for Zep to process the run's memories before a
    # report may start anyway (every batch has been delivered by then; Zep finishes on its own)
    MEMORY_WAIT_BEFORE_REPORT_SECONDS = int(os.environ.get('HIVEMIND_MEMORY_WAIT_SECONDS', '120'))
    # Report agent interviews: each person answers on both platforms, and under API rate limits a
    # batch of 6 took about 3.5 minutes on the live site, longer than the old fixed 180 s wait.
    REPORT_MAX_INTERVIEWS = int(os.environ.get('HIVEMIND_REPORT_MAX_INTERVIEWS', '4'))
    REPORT_INTERVIEW_TIMEOUT_SECONDS = int(os.environ.get('HIVEMIND_INTERVIEW_TIMEOUT_SECONDS', '420'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # Actions available on each OASIS platform
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report agent
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """Check that the required settings are present."""
        errors: list[str] = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not set")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not set")
        if os.environ.get("ZEP_API_URL"):
            errors.append("ZEP_API_URL is not supported; only Zep Cloud is supported")
        if cls.DEBUG:
            import warnings
            warnings.warn("Flask DEBUG mode is enabled. Do not use in production.", RuntimeWarning)
        return errors
