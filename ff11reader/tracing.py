"""Local, bounded operation timings. Payloads and exception messages are excluded."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import json
import logging
from logging.handlers import RotatingFileHandler
from time import perf_counter_ns
from uuid import uuid4

_current = ContextVar('trace_span', default=None)
_logger = None

def configure(path):
    global _logger
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.handleError = lambda record: None
        logger = logging.Logger('ff11.timings', level=logging.INFO)
        logger.addHandler(handler)
        previous = _logger
        _logger = logger
        if previous:
            for old in previous.handlers: old.close()
    except Exception:
        pass

@contextmanager
def span(name):
    if _logger is None:
        yield
        return
    parent = _current.get()
    identity = uuid4().hex
    operation = parent[0] if parent else identity
    token = _current.set((operation, identity))
    started = datetime.now(timezone.utc).isoformat()
    clock = perf_counter_ns()
    status = 'ok'
    error = None
    try:
        yield
    except BaseException as exc:
        status = 'error'
        error = type(exc).__name__
        raise
    finally:
        elapsed = (perf_counter_ns() - clock) / 1_000_000
        _current.reset(token)
        try:
            _logger.info(json.dumps(dict(operation_id=operation, span_id=identity,
                parent_id=parent[1] if parent else None, name=name, started=started,
                elapsed_ms=round(elapsed,3), status=status, error_type=error)))
        except Exception:
            pass

def traced(name):
    def decorate(function):
        @wraps(function)
        def call(*args, **kwargs):
            with span(name): return function(*args, **kwargs)
        return call
    return decorate
