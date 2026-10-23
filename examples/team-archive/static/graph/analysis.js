import {t as boTranslate} from './i18n.js';
// View selection is a projection. It cannot add permission, call or runtime facts.
import { viewTypes, relationType, stateNodeId } from './graph-core.js';
const types = ['business', 'function', 'state', 'decision', 'resource', 'data', 'effect', 'wait'];
const edges = ['call', 'flow', 'transition', 'guard', 'data', 'resource', 'join', 'shared', 'other'];
export const presets = [
    { id: 'overview', label: boTranslate("Layered overview"), hierarchical: true, nodes: types, edges },
    { id: 'business', label: boTranslate("Business flow"), nodes: ['business'], edges: ['flow', 'guard', 'data', 'join'] },
    { id: 'states', label: boTranslate("State machine"), nodes: ['state'], edges: ['transition'] },
    { id: 'functions', label: boTranslate("Functions and parameters"), nodes: ['function', 'decision', 'data'], edges: ['call', 'data'] },
    { id: 'permission', label: boTranslate("Authorization"), nodes: ['business', 'decision', 'function', 'data', 'wait'], edges: ['guard', 'data', 'call', 'flow'], scope: 'permission' },
    { id: 'resources', label: boTranslate("Concurrency and resources"), nodes: ['function', 'resource', 'decision', 'state', 'wait', 'data'], edges: ['resource', 'join', 'transition', 'data'], scope: 'execution' },
    { id: 'data', label: boTranslate("Data dependencies"), nodes: ['function', 'decision', 'data', 'effect'], edges: ['data', 'guard', 'call'] },
    { id: 'runtime', label: boTranslate("Observed execution"), nodes: types, edges, scope: 'observed' },
    { id: 'blocked', label: boTranslate("Waiting and failures"), nodes: types, edges, scope: 'blocked' },
    { id: 'shared', label: boTranslate("Shared membership"), nodes: types, edges: ['shared'], scope: 'shared' },
];
export function cleanProfile(value) {
    const strings = (values, allowed) => Array.isArray(values) ? [...new Set(values.filter(x => allowed.includes(x)))] : allowed.slice();
    return { nodes: strings(value?.nodes, types), edges: strings(value?.edges, edges),
        regions: strings(value?.regions, types), depth: Number.isInteger(value?.depth) ? value.depth : 'all',
        scope: ['all', 'permission', 'execution', 'observed', 'blocked', 'shared'].includes(value?.scope) ? value.scope : 'all',
        query: typeof value?.query === 'string' ? value.query.trim().slice(0, 100) : '', hierarchical: value?.hierarchical === true };
}
export function profileFor(id, custom = []) { return cleanProfile(presets.find(p => p.id === id) || custom.find(p => p.id === id) || presets[0]); }
export function matchingNodes(all, view, events, profile, statusOf, relations = view.model.edges) {
    const profileTypes = new Set(profile.nodes), selected = new Set(), execution = view.model.machine.execution || {};
    const scopeNodes = new Set(), raw = relations;
    if (profile.scope === 'permission') {
        for (const n of all.values())
            if (n.semantic_roles?.includes('permission'))
                scopeNodes.add(n.id);
        const seeds = new Set(scopeNodes);
        for (const e of raw)
            if (['guard', 'data'].includes(e.type) && (seeds.has(e.to) || seeds.has(e.from))) {
                scopeNodes.add(e.from);
                scopeNodes.add(e.to);
            }
    }
    if (profile.scope === 'execution') {
        for (const n of all.values())
            if (n.execution_role)
                scopeNodes.add(n.id);
        for (const n of [...(execution.activities || []), ...(execution.resources || []), execution.join].filter(Boolean))
            scopeNodes.add(n.id);
        if (execution.within)
            scopeNodes.add(stateNodeId(view.model, execution.within));
    }
    const eventIds = new Set(events.map(e => e.node));
    for (const n of all.values()) {
        const canonical = n.referenceOf || n.id;
        let inScope = profile.scope === 'all';
        if (['permission', 'execution'].includes(profile.scope))
            inScope = scopeNodes.has(canonical) || scopeNodes.has(n.event_node) || scopeNodes.has(n.parent);
        if (profile.scope === 'observed')
            inScope = eventIds.has(n.event_node || canonical);
        if (profile.scope === 'blocked')
            inScope = statusOf(n) === 'blocked';
        if (profile.scope === 'shared')
            inScope = !!n.referenceOf || [...all.values()].some(ref => ref.referenceOf === n.id || ref.referenceOf && ref.parent === n.id);
        const query = profile.query.toLocaleLowerCase();
        const matches = !query || [n.label, n.id, n.source?.symbol, n.summary].join(' ').toLocaleLowerCase().includes(query);
        const depthMatches = profile.depth === 'all' || n.projection_depth === profile.depth;
        if (viewTypes(n).some(type => profileTypes.has(type)) && inScope && matches && depthMatches)
            selected.add(n.id);
    }
    for (const id of selected) {
        const n = all.get(id);
        if (n.referenceOf && !selected.has(n.parent))
            selected.delete(id);
    }
    // Keep the real endpoint of an allowed relation as a labelled boundary. This
    // is one hop from the selection, never a transitive permission/call shortcut.
    const seeds = new Set(selected), context = new Set();
    for (const e of raw) {
        if (!profile.edges.includes(relationType(e)) || e.type === 'contains')
            continue;
        for (const [from, to] of [[e.from, e.to], [e.to, e.from]])
            if (seeds.has(from) && !seeds.has(to) && all.has(to)) {
                if (e.origin === 'capture-field' && all.get(to).field)
                    continue;
                context.add(to);
            }
    }
    for (const id of context)
        selected.add(id);
    selected.contextIds = context;
    return selected;
}
export function sharedMemberships(model) {
    const memberships = [...(model.presentation?.memberships || [])], execution = model.machine.execution;
    if (execution?.within) {
        const group = stateNodeId(model, execution.within);
        for (const n of [...(execution.activities || []), ...(execution.resources || []), execution.join].filter(Boolean))
            memberships.push({ group, member: n.id, reason: boTranslate("Internal execution configuration for this state"), evidence: 'machine.execution' });
    }
    const seen = new Set();
    return memberships.filter(m => { const key = m.group + '\0' + m.member; if (m.group === m.member || seen.has(key))
        return false; seen.add(key); return true; });
}
