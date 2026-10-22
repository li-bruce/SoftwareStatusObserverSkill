"""Compatibility entry; implementation belongs to the independent state module."""
try:
    from .bo_runtime import resolve
except ImportError:
    from bo_runtime import resolve

_core = resolve(__file__, __name__, 'bo_stategraph.execution_contract')
globals().update({k: v for k, v in vars(_core).items() if not k.startswith('__')})
if __name__ == '__main__' and hasattr(_core, 'main'):
    _core.main()
