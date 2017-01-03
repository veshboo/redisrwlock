import logging
from .redisrwlock import _cmp_time, Rwlock, RwlockClient

# Set default logging handler to avoid "No handler found" warnings.
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:  # pragma: no cover
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.getLogger(__name__).addHandler(NullHandler())
__all__ = [_cmp_time, Rwlock, RwlockClient]
