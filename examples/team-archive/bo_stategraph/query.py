"""Project state projection. Reads committed storage; never maintains a second state."""
from copy import deepcopy


def bo_machine(snapshot, build_id):
    configurations = []
    for run in snapshot['runs']:
        config = deepcopy(run['configuration'])
        config.update(phase=run['phase'], disposition=run['phase'] if run['phase'] in
            ('superseded', 'interrupted', 'cancelled') else 'current', qualification=run['qualification'],
            stop_reason=run['stop_reason'], resume_required=run['resume_required'],
            state_revision=run.get('state_revision'), run_build_id=run.get('execution_version'),
            source_status='current' if run.get('execution_version') == build_id else 'unbound')
        config['context'] = {'param_version': run['input']['content_version'],
            'capacity': config['resources']['processing_slots']['capacity'], 'operator_id': run['input']['operator_id'],
            'document_id': run['input']['document_id']}
        configurations.append(config)
    latest = snapshot['runs'][-1] if snapshot['runs'] else None
    return {'current': latest['phase'] if latest else 'created', 'configurations': configurations,
            'journal': [j for run in snapshot['runs'] for j in run['phase_journal']]}
