"""Check the shipped Skill, relative documentation links and copied runtime."""
from pathlib import Path
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
    missing = []
    for source in [*ROOT.glob('README*.md'), *ROOT.glob('docs/*.md'), *ROOT.glob('examples/delivery/README*.md'),
                   *SKILL.rglob('*.md')]:
        for target in re.findall(r'\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
            if target.startswith(('http:', 'https:', '#', 'mailto:')) or '<' in target:
                continue
            target = target.split('#')[0]
            if target and not (source.parent/target).exists():
                missing.append(f'{source.relative_to(ROOT)} -> {target}')
    assert not missing, '\n'.join(missing)
    for folder in (SKILL, ROOT/'examples/delivery'):
        for license in folder.rglob('PIXI-LICENSE.txt'):
            assert 'Mathew Groves' in license.read_text(), 'PixiJS attribution missing'
    print(f'Package references and {len(scripts)} copied runtime modules match.')


if __name__ == '__main__':
    check()
