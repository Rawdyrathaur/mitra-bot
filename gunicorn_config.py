"""
Gunicorn Configuration for Production
"""
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'  # Use 'gevent' or 'eventlet' for async workers
worker_connections = 1000
max_requests = 1000  # Restart workers after this many requests (prevents memory leaks)
max_requests_jitter = 50  # Add randomness to max_requests
timeout = 30  # Worker timeout in seconds
keepalive = 2  # Keep-alive connections

# Server mechanics
daemon = False  # Run in foreground
pidfile = None  # PID file location
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
accesslog = os.getenv('ACCESS_LOG', '-')  # '-' means stdout
errorlog = os.getenv('ERROR_LOG', '-')    # '-' means stderr
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'mitra-bot'

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized"""
    print("Mitra Bot starting...")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP"""
    print("Reloading Mitra Bot...")


def when_ready(server):
    """Called just after the server is started"""
    print(f"Mitra Bot ready. Listening on {bind}")


def on_exit(server):
    """Called just before exiting Gunicorn"""
    print("Mitra Bot shutting down...")


def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT"""
    print(f"Worker {worker.pid} interrupted")


def pre_fork(server, worker):
    """Called just before a worker is forked"""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked"""
    print(f"Worker {worker.pid} spawned")


def post_worker_init(worker):
    """Called just after a worker has initialized the application"""
    pass


def worker_exit(server, worker):
    """Called just after a worker has been exited"""
    print(f"Worker {worker.pid} exited")


# SSL (if needed)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'
# ca_certs = '/path/to/ca_certs'
# cert_reqs = 0  # ssl.CERT_NONE
# ssl_version = 3  # ssl.PROTOCOL_TLSv1_2
# ciphers = 'TLS_AES_256_GCM_SHA384:...'

# Security
limit_request_line = 4096  # Max size of HTTP request line
limit_request_fields = 100  # Max number of header fields
limit_request_field_size = 8190  # Max size of HTTP request header field

# Debugging (disable in production)
reload = os.getenv('FLASK_ENV') == 'development'
spew = False  # Install a trace function
check_config = False

# Environment variables
raw_env = []  # List of environment variables in the form KEY=VALUE
