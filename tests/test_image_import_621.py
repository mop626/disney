import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('image_import_621', PROJECT_ROOT / 'image_import_621.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestImageImport621(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)
        (self.root / 'images' / 'new-candidates').mkdir(parents=True)
        shutil.copy2(PROJECT_ROOT / 'new_characters.json', self.root / 'new_characters.json')
        self.existing = {
            'old-' + str(i): {
                'path': f'images/old-{i}.webp',
                'reviewed': True, 'singleCharacter': True,
                'characterId': f'old-{i}'
            }
            for i in range(200)
        }
        (self.root / 'images' / 'manifest.json').write_text(json.dumps(self.existing), encoding='utf8')
        self.originals = {}
        for key in ('ROOT', 'TARGETS_FILE', 'MANIFEST_FILE', 'CANDIDATE_DIR', 'INDEX_FILE', 'DECISIONS_FILE', 'REPORT_FILE'):
            self.originals[key] = getattr(module, key)
        module.ROOT = self.root
        module.TARGETS_FILE = self.root / 'new_characters.json'
        module.MANIFEST_FILE = self.root / 'images' / 'manifest.json'
        module.CANDIDATE_DIR = self.root / 'images' / 'new-candidates'
        module.INDEX_FILE = module.CANDIDATE_DIR / 'index.json'
        module.DECISIONS_FILE = module.CANDIDATE_DIR / 'approvals.json'
        module.REPORT_FILE = module.CANDIDATE_DIR / 'status.csv'
        self.addCleanup(self.restore)
        im = Image.new('RGB', (240, 220), '#e8b465')
        b = io.BytesIO()
        im.save(b, format='WEBP', quality=80)
        self.image = b.getvalue()

    def restore(self):
        for k, v in self.originals.items():
            setattr(module, k, v)

    def test_normalize_and_score(self):
        self.assertEqual(module.normalized('José Carioca'), 'josecarioca')
        self.assertEqual(module.normalized('Inside Out II'), 'insideout2')
        self.assertEqual(module.candidate_score({'name': 'Pete', 'films': ['Mickey & Friends']}, {'name': 'Pete', 'films': ['Mickey Mouse']}), 50)
        self.assertEqual(module.candidate_score({'name': 'Pete', 'films': ['Mickey & Friends']}, {'name': 'Other Pete', 'films': ['Mickey & Friends']}), 0)
        self.assertEqual(module.candidate_score({'name': 'Rapunzel', 'films': ['Tangled']}, {'name': 'Rapunzel', 'films': ['Tangled (2010 film)']}), 100)

    def test_fetch_and_publish_only_selected_while_preserving_200_images(self):
        names = json.loads((self.root / 'new_characters.json').read_text(encoding='utf8'))
        first, second = names[:2]
        api = [
            {'_id': 9101, 'name': first['name'], 'imageUrl': 'https://static.wikia.nocookie.net/disney/images/a/a.png', 'films': ['Other film'], 'sourceUrl': 'https://disney.fandom.com/wiki/Pete'},
            {'_id': 9102, 'name': second['name'], 'imageUrl': 'https://static.wikia.nocookie.net/disney/images/b/b.png', 'films': ['Other film'], 'sourceUrl': 'https://disney.fandom.com/wiki/Horace'},
        ]
        with patch.object(module, 'get_api_characters', return_value=api), patch.object(module, 'try_image_url', return_value=(self.image, (240, 220))):
            module.fetch_images(limit=2, workers=1, max_pages=1)
        ix = module.read_json(module.INDEX_FILE)
        self.assertEqual(len(ix['characters'][first['id']]['candidates']), 1)
        self.assertEqual(len(ix['characters'][second['id']]['candidates']), 1)
        self.assertEqual(module.read_json(module.MANIFEST_FILE), self.existing, 'fetch must never modify approved manifest')
        selected = ix['characters'][first['id']]['candidates'][0]['path']
        module.write_json(module.DECISIONS_FILE, {'version': 1, 'approved': [{'characterId': first['id'], 'path': selected}]})
        module.publish_approvals()
        manifest = module.read_json(module.MANIFEST_FILE)
        self.assertEqual(len(manifest), 201)
        self.assertEqual({key: manifest[key] for key in self.existing}, self.existing)
        self.assertTrue(manifest[first['id']]['reviewed'])
        self.assertTrue(manifest[first['id']]['singleCharacter'])
        self.assertTrue((self.root / manifest[first['id']]['path']).is_file())
        self.assertNotIn(second['id'], manifest)
        # Repeat publish must not overwrite or duplicate an already approved image.
        module.publish_approvals()
        self.assertEqual(len(module.read_json(module.MANIFEST_FILE)), 201)

    def test_tampered_candidate_is_never_published(self):
        names = json.loads((self.root / 'new_characters.json').read_text(encoding='utf8'))
        cid = names[0]['id']
        path = 'images/new-candidates/' + cid + '--99.webp'
        (self.root / path).write_bytes(self.image)
        module.write_json(module.INDEX_FILE, {'version': 1, 'characters': {cid: {'candidates': [{'path': path, 'sha256': 'bad-hash'}]}}})
        module.write_json(module.DECISIONS_FILE, {'version': 1, 'approved': [{'characterId': cid, 'path': path}]})
        with self.assertRaises(RuntimeError):
            module.publish_approvals()
        self.assertEqual(module.read_json(module.MANIFEST_FILE), self.existing)


if __name__ == '__main__':
    unittest.main()
