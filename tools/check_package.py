"""Check the shipped Skill, relative documentation links and copied runtime."""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills/business-observer'


def check():
    text = (SKILL/'SKILL.md').read_text(encoding='utf-8')
    assert text.startswith('---\nname: business-observer\n'), 'Skill identity/frontmatter missing'
    assert re.search(r'^description: .+', text, re.M), 'Skill trigger description missing'
    scripts = list((SKILL/'scripts').glob('*.py'))
    for source in scripts:
        copy = ROOT/'examples/delivery/observer_generated/runtime'/source.name
        assert source.read_bytes() == copy.read_bytes(), f'Runtime copy is stale: {source.name}'
        trial_copy = ROOT/'examples/team-archive/observer_runtime'/source.name
        assert source.read_bytes() == trial_copy.read_bytes(), f'Archive runtime copy is stale: {source.name}'
    assets = SKILL/'assets/stategraph-viewer'
    for name in ('graph-core.js', 'layout.js', 'viewer.js', 'viewer.css', 'index.html', 'elk.bundled.js', 'elk-worker.min.js', 'ELK-LICENSE.md'):
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
    missing = []
    for source in [*ROOT.glob('README*.md'), *(ROOT/'docs').rglob('*.md'), *ROOT.glob('examples/*/README*.md'),
                   *SKILL.rglob('*.md')]:
        for target in re.findall(r'\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
            if target.startswith(('http:', 'https:', '#', 'mailto:')) or '<' in target:
                continue
            target = target.split('#')[0]
            if target and not (source.parent/target).exists():
                missing.append(f'{source.relative_to(ROOT)} -> {target}')
    assert not missing, '\n'.join(missing)
    for folder in (SKILL, ROOT/'examples/delivery', ROOT/'examples/team-archive'):
        for license in folder.rglob('PIXI-LICENSE.txt'):
            assert 'Mathew Groves' in license.read_text(encoding='utf-8'), 'PixiJS attribution missing'
    print(f'Package references and {len(scripts)} copied runtime modules match.')


if __name__ == '__main__':
    check()
