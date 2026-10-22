"""Validate an exported statechart contract, optionally against the runtime definition.

This checks declaration consistency, not guard truth, transactionality or equivalence.
"""
import argparse
import json
from pathlib import Path


try:
    from .bo_contracts import validate_chart
except ImportError:
    from bo_contracts import validate_chart


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('model');args=parser.parse_args()
    print(json.dumps(validate_chart(json.loads(Path(args.model).read_text(encoding='utf-8')))))
