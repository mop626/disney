import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

R = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('image_search_fallback_621', R / 'image_search_fallback_621.py')
import sys
sys.path.insert(0, str(R))
fallback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallback)
core = fallback.core

class FallbackSearchTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        (self.root/'images'/'new-candidates').mkdir(parents=True)
        shutil.copy2(R/'new_characters.json', self.root/'new_characters.json')
        shutil.copytree(R/'manual-provided', self.root/'manual-provided')
        old = {f'old-{i}': {'path': f'images/old-{i}.webp',
                              'reviewed': True, 'singleCharacter': True,
                              'characterId': f'old-{i}'} for i in range(200)}
        (self.root/'images'/'manifest.json').write_text(json.dumps(old), encoding='utf8')
        self.old = old
        self.keys = {'fallback': {}, 'core': {}}
        for k in ('ROOT','SEEDS','SEED_MAP','CANDIDATES','INDEX','MANIFEST','TARGETS','REPORT'):
            self.keys['fallback'][k] = getattr(fallback,k)
        for k in ('ROOT','TARGETS_FILE','MANIFEST_FILE','CANDIDATE_DIR','INDEX_FILE','DECISIONS_FILE','REPORT_FILE'):
            self.keys['core'][k] = getattr(core,k)
        fallback.ROOT = self.root
        fallback.SEEDS = self.root/'manual-provided'
        fallback.SEED_MAP = fallback.SEEDS/'seed-metadata.json'
        fallback.CANDIDATES = self.root/'images'/'new-candidates'
        fallback.INDEX = fallback.CANDIDATES/'index.json'
        fallback.MANIFEST = self.root/'images'/'manifest.json'
        fallback.TARGETS = self.root/'new_characters.json'
        fallback.REPORT = fallback.CANDIDATES/'fallback-research.csv'
        core.ROOT = self.root
        core.TARGETS_FILE = self.root/'new_characters.json'
        core.MANIFEST_FILE = fallback.MANIFEST
        core.CANDIDATE_DIR = fallback.CANDIDATES
        core.INDEX_FILE = fallback.INDEX
        core.DECISIONS_FILE = fallback.CANDIDATES/'approvals.json'
        core.REPORT_FILE = fallback.CANDIDATES/'status.csv'
        self.addCleanup(self.restore)
        im=Image.new('RGB',(280,250),(100,170,210))
        b=io.BytesIO();im.save(b,format='WEBP',quality=80);self.image=b.getvalue()

    def restore(self):
        for key,val in self.keys['fallback'].items():setattr(fallback,key,val)
        for key,val in self.keys['core'].items():setattr(core,key,val)

    def test_manual_images_are_unreviewed_and_original_manifest_unchanged(self):
        with patch.object(fallback,'find_wiki_images',return_value=[]):
            fallback.run(limit=1,pause=0)
        index=json.loads(fallback.INDEX.read_text())['characters']
        for row in json.loads(fallback.SEED_MAP.read_text()):
            self.assertTrue(any(x['path'].endswith('--user-reference.webp') for x in index[row['characterId']]['candidates']))
            self.assertFalse(index[row['characterId']]['candidates'][0]['filmMatch'])
        self.assertEqual(json.loads(fallback.MANIFEST.read_text()),self.old)
        self.assertTrue(fallback.REPORT.exists())

    def test_secondary_source_creates_candidate_without_auto_approval(self):
        target = json.loads((self.root/'new_characters.json').read_text())
        cid='extended-mickey-friends-magica-de-spell'
        sample={'title':'Magica De Spell','pageid':12345,'src':'https://static.wikia.nocookie.net/disney/images/a/abc.png'}
        with patch.object(fallback,'find_wiki_images',return_value=[sample]),\
             patch.object(core,'try_image_url',return_value=(self.image,(280,250))):
            fallback.run(limit=5,pause=0)
        index=json.loads(fallback.INDEX.read_text())['characters']
        # The first eligible list starts with Max Goof, Magica may appear after; test direct fallback candidate instead.
        self.assertEqual(json.loads(fallback.MANIFEST.read_text()),self.old)
        auto=[x for v in index.values() for x in v.get('candidates',[]) if '--wiki-' in x['path']]
        self.assertGreaterEqual(len(auto),1)
        self.assertEqual(auto[0]['reviewRequired'],True)
        self.assertTrue((self.root/auto[0]['path']).is_file())
        self.assertTrue(all(x.get('publishedPath','')=='' for x in auto))

    def test_repeat_seed_is_idempotent(self):
        with patch.object(fallback,'find_wiki_images',return_value=[]):
            fallback.run(limit=0,pause=0)
        before=json.loads(fallback.INDEX.read_text())
        with patch.object(fallback,'find_wiki_images',return_value=[]):
            fallback.run(limit=0,pause=0)
        after=json.loads(fallback.INDEX.read_text())
        for k in before['characters']:
            self.assertEqual(len(before['characters'][k]['candidates']),len(after['characters'][k]['candidates']))

    def test_link_and_title_variants(self):
        t={'name':'Grand Duke','films':['Cinderella']}
        self.assertIn('The Grand Duke',fallback.suggest_page_titles(t))
        self.assertIn('Cinderella',fallback.image_search_url('Grand Duke','Cinderella'))
        self.assertIn('Magica_De_Spell',fallback.wiki_page('Magica De Spell'))

    def test_publish_existing_importer_can_accept_manual_candidate(self):
        with patch.object(fallback,'find_wiki_images',return_value=[]):
            fallback.run(limit=0,pause=0)
        cid='extended-cinderella-grand-duke'
        c=json.loads(fallback.INDEX.read_text())['characters'][cid]['candidates'][0]
        core.write_json(core.DECISIONS_FILE, {'version':1,'approved':[{'characterId':cid,'path':c['path']}]})
        core.publish_approvals()
        new=json.loads(fallback.MANIFEST.read_text())
        self.assertEqual(len(new),201)
        self.assertTrue(new[cid]['reviewed'])
        self.assertEqual({k:new[k] for k in self.old},self.old)

if __name__=='__main__':unittest.main()
