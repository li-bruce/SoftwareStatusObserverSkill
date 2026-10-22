"""Optional graph Web surface: design dialogue, visibility and core delivery.

This module never imports the business engine. Disabling Web is independent of
collection, Python state queries and executable state definitions.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

try:
    from .bo_design import BODesign
    from .behavior_model import contained
    from .requirements_dialogue import read
    from .sync_io import write
    from .view_preferences import Preferences, PreferenceConflict, file_lock
except ImportError:
    from bo_design import BODesign
    from behavior_model import contained
    from requirements_dialogue import read
    from sync_io import write
    from view_preferences import Preferences, PreferenceConflict, file_lock


ASSETS = Path(__file__).resolve().parents[1] / 'assets/stategraph-viewer'
MODES = {'visible', 'hidden', 'disabled'}
WEB_APIS = ('/api/view', '/api/source', '/api/preferences', '/api/recordings',
            '/api/stategraph', '/api/versions', '/api/design')


class BOWeb:
    def __init__(self, root, *, assets=ASSETS, discovery=None, graph_routes=('/graph', '/graph/')):
        self.root = Path(root).absolute().resolve()
        self.assets = Path(assets)
        if self.assets == ASSETS and not self.assets.is_dir():
            self.assets = next((self.root / p for p in ('static/graph', 'observer_generated/static', 'integrations/bo_view')
                                if (self.root / p / 'index.html').is_file()), self.assets)
        self.config = contained(self.root, 'bo_stategraph/config/web.json')
        self.design = BODesign(self.root, discovery)
        self.graph_routes = set(graph_routes)

    def status(self):
        value = read(self.config) if self.config.exists() else {'schema': 1, 'mode': 'visible'}
        if not isinstance(value, dict) or value.get('schema') != 1 or value.get('mode') not in MODES or set(value) != {'schema', 'mode'}:
            raise ValueError('Web 配置无效；mode 必须为 visible、hidden 或 disabled')
        return {**value, 'entry_visible': value['mode'] == 'visible', 'enabled': value['mode'] != 'disabled'}

    def set_mode(self, mode):
        if mode not in MODES: raise ValueError('未知的 Web 模式')
        with file_lock(self.config.with_suffix('.lock')):
            self.status()  # Do not replace a malformed configuration silently.
            write(self.config, {'schema': 1, 'mode': mode})
        return self.status()

    def allowed(self, path):
        graph = (path in self.graph_routes or
                 any(path == prefix or path.startswith(prefix + '/') for prefix in WEB_APIS) or
                 path.startswith('/api/bo/') or
                 path.startswith('/') and '/' not in path[1:] and (self.assets / path[1:]).is_file())
        return not graph or self.status()['enabled']

    def entry_html(self, raw):
        if self.status()['entry_visible']: return raw
        return raw.replace(b'data-bo-entry', b'data-bo-entry hidden')

    def get(self, path):
        if path == '/api/design': return self.design.snapshot()
        return None



def bo_serve(root, *, port=8830, discovery=None, assets=ASSETS):
    web = BOWeb(root, assets=assets, discovery=discovery, graph_routes=('/', '/graph', '/graph/'))
    root = web.root
    initial = web.design.view()  # Validate before listening; no fabricated business engine.
    if not web.status()['enabled']: raise ValueError('Web 已关闭；先用 mode visible 恢复')
    cfg = read(Path(root) / 'sync.json') if (Path(root) / 'sync.json').exists() else {}
    preferences = Preferences(root, initial['layout_id'], legacy_project_ids=cfg.get('view_preferences_legacy_ids', []))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, code, body, mime='application/json'):
            raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            for key, value in [('Content-Type', mime + '; charset=utf-8'), ('Content-Length', str(len(raw))),
                               ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')]: self.send_header(key, value)
            self.end_headers(); self.wfile.write(raw)
        def local(self):
            hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            origin = self.headers.get('Origin')
            return self.headers.get('Host') in hosts and (not origin or origin == 'http://' + self.headers['Host'])
        def do_GET(self):
            if not self.local(): return self.reply(403, {'error': '仅接受本地同源请求'})
            path = urlsplit(self.path).path
            try:
                if not web.allowed(path): return self.reply(404, {'error': '调试 Web 已关闭', 'code': 'bo_web_disabled'})
                value = web.get(path)
                if value is not None: return self.reply(200, value)
                if path == '/api/view': return self.reply(200, web.design.view())
                if path == '/api/preferences': return self.reply(200, preferences.read())
                name = 'index.html' if path in web.graph_routes else path[1:]
                if not name or '/' in name or '\\' in name or name.startswith('.'):
                    return self.reply(404, {'error': '找不到页面'})
                file = web.assets / name
                if not file.is_file(): return self.reply(404, {'error': '找不到页面'})
                return self.reply(200, file.read_bytes(), mimetypes.guess_type(name)[0] or 'application/octet-stream')
            except (OSError, ValueError) as exc: return self.reply(400, {'error': str(exc)})
        def do_POST(self):
            if not self.local(): return self.reply(403, {'error': '仅接受本地同源请求'})
            path = urlsplit(self.path).path
            try:
                if not web.allowed(path): return self.reply(404, {'error': '调试 Web 已关闭', 'code': 'bo_web_disabled'})
                size = int(self.headers.get('Content-Length', 0))
                limit = 2 * 1024 * 1024 if path == '/api/preferences' else 32768
                if not 0 < size <= limit: raise ValueError('请求大小无效')
                value = json.loads(self.rfile.read(size))
                if not isinstance(value, dict): raise ValueError('请求必须是对象')
                if path == '/api/preferences': return self.reply(200, preferences.save(value))
                return self.reply(405, {'error': '图只供查看；请在开发工具的对话中提出修改'})
            except PreferenceConflict as exc: return self.reply(409, {'error': str(exc)})
            except (OSError, ValueError) as exc: return self.reply(400, {'error': str(exc)})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Design graph: http://127.0.0.1:{server.server_port}/graph', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['serve', 'status', 'mode', 'package'])
    p.add_argument('mode', nargs='?', choices=sorted(MODES))
    p.add_argument('--root', default='.')
    p.add_argument('--port', type=int, default=8830)
    p.add_argument('--assets', type=Path, default=ASSETS)
    p.add_argument('--discovery')
    p.add_argument('--out')
    a = p.parse_args()
    try:
        if a.action == 'serve': bo_serve(a.root, port=a.port, discovery=a.discovery, assets=a.assets); return 0
        if a.action == 'package':
            if not a.out: raise ValueError('package 需要 --out 指定新的项目内 ZIP 路径')
            return subprocess.call([sys.executable, str(Path(__file__).with_name('architecture_guard.py')),
                                    'package', '--root', a.root, '--out', a.out])
        web = BOWeb(a.root)
        if a.action == 'mode' and not a.mode: raise ValueError('请选择 Web 模式')
        print(json.dumps(web.set_mode(a.mode) if a.action == 'mode' else web.status(), ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__': raise SystemExit(main())
