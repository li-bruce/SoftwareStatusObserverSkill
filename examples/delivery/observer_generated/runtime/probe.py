"""Public entry point; implementation: bo_observer.observation.probe."""
import importlib as _bo_importlib
import sys as _bo_sys
_bo_module = _bo_importlib.import_module((__package__ + '.' if __package__ else '') + 'bo_observer.observation.probe')
def __getattr__(name):
    return getattr(_bo_module, name)

if __name__ == '__main__':
    raise SystemExit(_bo_module.main())
else:
    _bo_sys.modules[__name__] = _bo_module
