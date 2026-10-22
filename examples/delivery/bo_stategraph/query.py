"""One projection of committed execution configurations for query and export."""
from copy import deepcopy


def bo_machine(job):
    configurations = deepcopy(job['executions'])
    return {'current': job['state'], 'journal': deepcopy(job['journal']), 'configurations': configurations}
