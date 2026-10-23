"""Check the shipped Skill, relative documentation links and copied runtime."""
from pathlib import Path
import hashlib
import re
import sys
from document_links import document_link_errors

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills/business-observer'


def check():
    sys.path.insert(0, str(SKILL/'scripts'))
    from bo_upgrade import bridge_source, CORE
    text = (SKILL/'SKILL.md').read_text(encoding='utf-8')
    assert text.startswith('---\nname: business-observer\n'), 'Skill identity/frontmatter missing'
    assert re.search(r'^description: .+', text, re.M), 'Skill trigger description missing'
    scripts = [p for p in (SKILL/'scripts').rglob('*') if p.is_file() and
               p.suffix in {'.py','.mjs','.json'} and not set(p.parts)&{'__pycache__','node_modules'}]
    for project in ('delivery','team-archive','python-modes'):
        for source, target in [('bo_stategraph.py','__init__.py'),('bo_contracts.py','bo_contracts.py'),('execution_contract.py','execution_contract.py')]:
            assert (SKILL/'scripts'/source).read_bytes() == (ROOT/'examples'/project/'bo_stategraph'/target).read_bytes(), f'State module copy stale: {project}/{target}'
    assert (SKILL/'scripts/bo_stategraph.py').read_bytes() == (ROOT/'examples/python-modes/bo_stategraph/__init__.py').read_bytes(), 'Standalone Python module copy is stale'
    for source,target in [('bo_observer/adapters/javascript/bo_runtime.mjs','bo_runtime.mjs'),
        ('bo_observer/adapters/python/bo_executor.py','bo_executor.py'),('bo_observer/adapters/python/bo_probe.py','bo_probe.py'),
        ('bo_contracts.py','bo_contracts.py'),('execution_contract.py','execution_contract.py')]:
        assert (SKILL/'scripts'/source).read_bytes()==(ROOT/'examples/multilanguage/bo_stategraph'/target).read_bytes(), 'Native adapter copy stale: '+target
    for source in scripts:
        name=source.relative_to(SKILL/'scripts')
        copy = ROOT/'examples/delivery/observer_generated/runtime'/name
        expected = bridge_source(source.name) if source.name in CORE else source.read_bytes()
        assert expected == copy.read_bytes(), f'Runtime copy is stale: {source.name}'
        trial_copy = ROOT/'examples/team-archive/observer_runtime'/name
        assert expected == trial_copy.read_bytes(), f'Archive runtime copy is stale: {source.name}'
    assets = SKILL/'assets/stategraph-viewer'
    for directory in ('examples/delivery/integrations/bo_view','examples/team-archive/static/graph','examples/delivery/observer_generated/static'):
        for asset in assets.iterdir():
            if asset.is_file(): assert asset.read_bytes() == (ROOT/directory/asset.name).read_bytes(), f'Viewer copy stale: {directory}/{asset.name}'
    for name in ('preferences.js', 'graph-core.js', 'layout.js', 'analysis.js', 'data-layer.js', 'recording.js', 'replay-steps.js', 'glyphs.js', 'viewer.js', 'viewer.css', 'index.html', 'elk.bundled.js', 'elk-worker.min.js', 'ELK-LICENSE.md'):
        assert (assets/name).read_bytes() == (ROOT/'examples/delivery/observer_generated/static'/name).read_bytes(), f'Graph template copy is stale: {name}'
    # Reviewed open-source distributions. Revisit provenance/licenses on upgrades.
    bundles = {
        'pixi.min.js': '06d9ef9823e743518793083c296d801e752db128cb1f519fbabe37e1259567ea',
        'elk.bundled.js': '1222e44f953ce7746af23801e723708f8e6f436b8b377a6a5fc7552f34a307b3',
        'elk-worker.min.js': 'e4f5c51c6f2fd564bb64e52e81c4a85a316ef2f24f8b90e1db5eb886c765b030',
    }
    for directory in (assets, ROOT/'examples/delivery/observer_generated/static', ROOT/'examples/team-archive/static/graph'):
        for name, digest in bundles.items():
            assert hashlib.sha256((directory/name).read_bytes()).hexdigest() == digest, f'Review changed viewer dependency: {name}'
        assert 'Eclipse Public License - v 2.0' in (directory/'ELK-LICENSE.md').read_text(encoding='utf-8'), 'ELK license missing'
        assert 'The MIT License' in (directory/'PIXI-LICENSE.txt').read_text(encoding='utf-8'), 'PixiJS license missing'
    page = (assets/'index.html').read_text(encoding='utf-8')
    assert set(re.findall(r'<script[^>]+src="([^"]+)"', page)) == {'/pixi.min.js', '/elk.bundled.js', '/viewer.js'}, 'Review new browser scripts and their licenses'
    sources = [source for source in [*ROOT.glob('README*.md'), *(ROOT/'docs').rglob('*.md'),
               *ROOT.glob('examples/*/README*.md'), *SKILL.rglob('*.md')]
               if not set(source.parts)&{'node_modules','__pycache__'}]
    missing = document_link_errors(ROOT, sources)
    assert not missing, '\n'.join(missing)
    for folder in (SKILL, ROOT/'examples/delivery', ROOT/'examples/team-archive'):
        for license in folder.rglob('PIXI-LICENSE.txt'):
            assert 'Mathew Groves' in license.read_text(encoding='utf-8'), 'PixiJS attribution missing'
    print(f'Package references and {len(scripts)} copied runtime modules match.')


if __name__ == '__main__':
    check()
