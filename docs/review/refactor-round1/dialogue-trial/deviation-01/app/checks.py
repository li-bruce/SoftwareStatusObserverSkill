"""Submitted dimensions in millimetres; no mesh parsing or orientation search."""
import math

def check_size(dimensions: list, limits: list) -> dict:
    failures = []
    if not isinstance(dimensions, list) or len(dimensions) != 3:
        return {"passed": False, "failures": ["dimensions: expected three axes"]}
    for axis, value, limit in zip(("length", "width", "height"), dimensions, limits):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            failures.append(axis + ": must be finite and positive")
        elif value > limit:
            failures.append(axis + ": exceeds printer limit")
    return {"passed": not failures, "failures": failures}

def check_material(material: str, supported: list) -> dict:
    passed = material in ("PLA", "ABS") and material in supported
    return {"passed": passed, "failures": [] if passed else ["material: unsupported by this printer"]}
