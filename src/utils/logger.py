"""
Production-ready logging configuration for Mitra Bot
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def setup_logger(name: str, log_file: str = None, level: str = None) -> logging.Logger:
    """
    Configure and return a logger with both file and console handlers

    Args:
        name: Logger name (usually __name__)
        log_file: Optional log file path
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Get log level from environment or parameter
    log_level = level or os.getenv('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level, logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # File handler with rotation (if log file specified)
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)

        # JSON formatter for file (production-ready)
        file_formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", '
            '"function": "%(funcName)s", "line": %(lineno)d, "message": "%(message)s"}',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Human-readable formatter for console
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with production configuration

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    log_file = os.getenv('LOG_FILE')
    return setup_logger(name, log_file)


# Request logging middleware
class RequestLogger:
    """Middleware for logging HTTP requests and responses"""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger(__name__)
        self.enabled = os.getenv('ENABLE_REQUEST_LOGGING', 'true').lower() == 'true'

    def __call__(self, environ, start_response):
        if not self.enabled:
            return self.app(environ, start_response)

        # Log request
        method = environ.get('REQUEST_METHOD')
        path = environ.get('PATH_INFO')
        query = environ.get('QUERY_STRING')
        remote_addr = environ.get('REMOTE_ADDR')

        self.logger.info(
            f"Request: {method} {path}{'?' + query if query else ''} from {remote_addr}"
        )

        return self.app(environ, start_response)


# Error tracking integration (Sentry, etc.)
def setup_error_tracking():
    """Setup error tracking integration (Sentry, etc.)"""
    sentry_dsn = os.getenv('SENTRY_DSN')

    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration

            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
                integrations=[FlaskIntegration()],
                traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
                profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.1'))
            )

            logger = get_logger(__name__)
            logger.info("Sentry error tracking initialized")

        except ImportError:
            logger = get_logger(__name__)
            logger.warning("Sentry SDK not installed. Error tracking disabled.")
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Failed to initialize Sentry: {e}")


# Security event logging
class SecurityLogger:
    """Logger for security-related events"""

    def __init__(self):
        self.logger = get_logger('security')

    def log_auth_attempt(self, email: str, success: bool, ip: str):
        """Log authentication attempt"""
        status = 'SUCCESS' if success else 'FAILED'
        self.logger.warning(f"Auth {status}: {email} from {ip}")

    def log_rate_limit_exceeded(self, ip: str, endpoint: str):
        """Log rate limit violation"""
        self.logger.warning(f"Rate limit exceeded: {ip} on {endpoint}")

    def log_invalid_token(self, ip: str):
        """Log invalid token usage"""
        self.logger.warning(f"Invalid token from {ip}")

    def log_permission_denied(self, user_id: str, resource: str, ip: str):
        """Log unauthorized access attempt"""
        self.logger.warning(f"Permission denied: User {user_id} tried to access {resource} from {ip}")


# Initialize security logger
security_logger = SecurityLogger()
