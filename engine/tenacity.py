"""
Tenacity stub — replaces the real tenacity library for offline environments.
In production, install the real tenacity: pip install tenacity>=8.2
The real library provides exponential backoff retry on network failures.
This stub makes the decorators pass-through so the engine can be tested.
"""

class _Noop:
    def __call__(self, *a, **kw):
        return self
    def __getattr__(self, name):
        return self

def stop_after_attempt(n): return _Noop()
def wait_exponential(**kw): return _Noop()
def retry_if_exception_type(exc): return _Noop()

def retry(stop=None, wait=None, retry=None, reraise=True):
    def decorator(fn):
        return fn
    return decorator
