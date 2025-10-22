from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry
from pythonjsonlogger import jsonlogger
import logging
from flask import Response

# Basic metrics
HTTP_REQUESTS = Counter('http_requests_total', 'HTTP requests', ['method', 'endpoint', 'status'])
HTTP_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['endpoint'])

# Domain-specific metrics (examples)
ONBOARDING_REQUESTS = Counter('onboarding_requests_total', 'Partner onboarding attempts')
ONBOARDING_SUCCESS = Counter('onboarding_success_total', 'Successful partner onboardings')
CONTRACT_VALIDATE_REQUESTS = Counter('contract_validate_requests_total', 'Contract validation attempts')


def configure_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    root = logging.getLogger()
    # Avoid adding duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(level)


def metrics_endpoint():
    """Return a Flask Response with current Prometheus metrics."""
    data = generate_latest()
    return Response(data, mimetype=CONTENT_TYPE_LATEST)
