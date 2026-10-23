import {t as boTranslate} from './i18n.js';
// A synchronous view cache backed by one project file. Only server acknowledgement
// means saved. Writes are serialized and revision conflicts never overwrite a peer.
export async function projectStorage(legacy, onStatus, request = fetch) {
    let document = null, error = '', timer = null, pending = false, writing = false, blocked = false;
    let state = boTranslate("Loading project views");
    const status = value => { state = value; onStatus?.(value); };
    try {
        const response = await request('/api/preferences', { cache: 'no-store' });
        if (!response.ok)
            throw Error('HTTP ' + response.status);
        document = await response.json();
        if (document.schema !== 1 || !document.entries)
            throw Error(boTranslate("Invalid preference format"));
        status(boTranslate("Project views loaded"));
    }
    catch (e) {
        error = String(e.message);
        blocked = true;
        status(boTranslate("Project views could not be loaded: ") + error);
    }
    const canMigrate = document?.revision === 0, entries = Object.assign(Object.create(null), document?.entries || {});
    let activeWrite = null;
    async function flush() {
        clearTimeout(timer);
        if (activeWrite) {
            await activeWrite;
            if (error || blocked) return false;
            return pending ? flush() : true;
        }
        if (blocked) return false;
        if (!pending) return true;
        activeWrite = write();
        try { await activeWrite; }
        finally { activeWrite = null; }
        if (error || blocked) return false;
        return pending ? flush() : true;
    }
    async function write() {
        writing = true;
        pending = false;
        const snapshot = { ...document, entries: { ...entries } };
        status(boTranslate("Saving to project\u2026"));
        try {
            const response = await request('/api/preferences', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(snapshot), keepalive: JSON.stringify(snapshot).length < 60000 });
            const result = await response.json();
            if (!response.ok) {
                blocked = response.status === 409;
                throw Error(result.error || 'HTTP ' + response.status);
            }
            document = result;
            status(boTranslate("View saved to project"));
        }
        catch (e) {
            error = String(e.message);
            pending = true;
            status(boTranslate("Not saved: ") + error);
        }
        finally {
            writing = false;
            if (pending && !error && !blocked)
                timer = setTimeout(flush, 150);
        }
    }
    function changed() { pending = true; error = ''; status(blocked ? boTranslate("View not saved; refresh and retry") : boTranslate("View has unsaved changes")); clearTimeout(timer); timer = setTimeout(flush, 180); }
    return {
        getItem(key) {
            if (Object.hasOwn(entries, key))
                return entries[key];
            if (canMigrate) {
                // Migrate only this project's layout prefix; unrelated browser data stays private.
                const base = key.replace(/:analysis$|:view:.*$/, '');
                try {
                    for (let i = 0; i < legacy.length; i++) {
                        const candidate = legacy.key(i);
                        if (candidate === base || candidate?.startsWith(base + ':')) {
                            const raw = legacy.getItem(candidate);
                            if (raw && typeof JSON.parse(raw) === 'object')
                                entries[candidate] = raw;
                        }
                    }
                    if (Object.hasOwn(entries, key))
                        changed();
                }
                catch { }
            }
            return entries[key] ?? null;
        },
        setItem(key, value) {
            if (entries[key] === value)
                return;
            entries[key] = value;
            try {
                legacy?.setItem(key, value);
            }
            catch { }
            changed();
        },
        flush, status: () => state
    };
}
