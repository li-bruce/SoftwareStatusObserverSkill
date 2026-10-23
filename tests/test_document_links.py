"""A public checkout must not depend on paths on the author's computer."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from document_links import document_link_errors


class DocumentLinksTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.validation').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.validation')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = self.root / 'dialogue.md'
        self.target = 'C:/original-project/design.md'
        self.doc.write_text(f'[Original design]({self.target})\n', encoding='utf-8')

    def catalog(self):
        path = self.root / 'docs/review/historical-links.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {'documents': [{'path': 'dialogue.md',
            'sha256': hashlib.sha256(self.doc.read_bytes()).hexdigest(),
            'references': [{'target': self.target, 'archive': 'evidence.zip',
                'member': 'project/design.md', 'context': 'Original transcript location.'}]}]}
        path.write_text(json.dumps(record), encoding='utf-8')
        with zipfile.ZipFile(self.root / 'evidence.zip', 'w') as archive:
            archive.writestr('project/design.md', 'Confirmed design')

    def test_unregistered_absolute_reference_fails_on_every_platform(self):
        self.assertTrue(document_link_errors(self.root, [self.doc]))

    def test_existing_local_file_does_not_make_a_portable_link(self):
        local = self.root / 'exists.md'
        local.write_text('Local', encoding='utf-8')
        self.doc.write_text(f'[Exists]({local.as_posix()})', encoding='utf-8')
        self.assertTrue(document_link_errors(self.root, [self.doc]))

    def test_original_transcript_and_archived_member_pass(self):
        self.catalog()
        self.assertEqual(document_link_errors(self.root, [self.doc]), [])

    def test_changed_transcript_cannot_reuse_historical_exception(self):
        self.catalog()
        self.doc.write_text(self.doc.read_text(encoding='utf-8') + 'Changed', encoding='utf-8')
        self.assertTrue(document_link_errors(self.root, [self.doc]))

    def test_missing_archived_member_fails(self):
        self.catalog()
        with zipfile.ZipFile(self.root / 'evidence.zip', 'w') as archive:
            archive.writestr('wrong.md', 'Wrong entry')
        self.assertTrue(document_link_errors(self.root, [self.doc]))

    def test_relative_missing_or_escaping_target_fails(self):
        self.doc.write_text('[Missing](missing.md) [Escape](../outside.md)', encoding='utf-8')
        self.assertEqual(len(document_link_errors(self.root, [self.doc])), 2)


if __name__ == '__main__':
    unittest.main()
