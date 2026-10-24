"""Resolve compatibility imports to the project's one independent state module."""

import importlib
import importlib.util
from pathlib import Path
import sys


def resolve(origin, imported_name, target):
    package = target.split(".")[0]
    root = next(
        (p for p in Path(origin).resolve().parents[:3] if (p / package / "__init__.py").is_file()),
        None,
    )
    if root is None:
        raise ImportError("Independent state module is missing; run the project migration first")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    elif sys.path[0] != str(root):
        sys.path.remove(str(root))
        sys.path.insert(0, str(root))
    if imported_name == target:
        # Older callers prepend the runtime folder to sys.path. Replace that
        # compatibility module with the actual package, retaining one identity.
        path = root / package / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            target, path, submodule_search_locations=[str(path.parent)]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[target] = module
        spec.loader.exec_module(module)
        return module
    return importlib.import_module(target)
