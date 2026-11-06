#!/usr/bin/env python3
"""Second-source search for missing Disney quiz image candidates.

IMPORTANT: Downloaded pictures are UNREVIEWED; this never changes manifest.json,
never approves a picture and never publishes to the playable quiz.

Additional source: Disney Wiki MediaWiki Action API (where accessible).
User-supplied solo-character pictures in manual-provided/ are added as options.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

import image_import_621 as core

ROOT = Path(__file__).resolve().parent
SEEDS = ROOT / 'manual-provided'
SEED_MAP = SEEDS / 'seed-metadata.json'
CANDIDATES = ROOT / 'images' / 'new-candidates'
INDEX = CANDIDATES / 'index.json'
MANIFEST = ROOT / 'images' / 'manifest.json'
TARGETS = ROOT / 'new_characters.json'
REPORT = CANDIDATES / 'fallback-research.csv'
WIKI_API = 'https://disney.fandom.com/api.php'
WIKI_BASE = 'https://disney.fandom.com/wiki/'
USER_AGENT = 'MagicalCharacterQuiz/2.0 (non-commercial image candidate research; manual review only)'


def wiki_page(title: str) -> str:
    return WIKI_BASE + quote(str(title).replace(' ', '_'), safe='()_-')


def image_search_url(name: str, film: str) -> str:
    return 'https://www.google.com/search?' + urlencode({'tbm': 'isch', 'q': f'Disney {film} {name} character'})


def api_get(params: dict, *, pause: float) -> dict:
    if pause:
        time.sleep(pause)
    url = WIKI_API + '?' + urlencode({'format': 'json', 'formatversion': '2', 'maxlag': '5', **params})
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urlopen(req, timeout=18) as response:
        if response.geturl().split('?', 1)[0] != WIKI_API:
            raise ValueError('Unexpected API redirect')
        raw = response.read(1_500_001)
        if len(raw) > 1_500_000:
            raise ValueError('API response exceeded size limit')
    body = json.loads(raw.decode('utf-8'))
    if not isinstance(body, dict) or body.get('error'):
        raise ValueError('Unexpected MediaWiki API response')
    return body


def suggest_page_titles(target: dict) -> list[str]:
    name = target['name'].strip()
    film = (target.get('films') or [''])[0]
    names = [name]
    if name.startswith('The '):
        names.append(name[4:])
    else:
        names.append('The ' + name)
    if name.lower() == 'grand duke':
        names.insert(0, 'The Grand Duke')
    if name.lower() in {'shenzi', 'banzai', 'ed'}:
        names.append('Shenzi, Banzai, and Ed')  # group image must be rejected by reviewer
    if film and film != 'Mickey & Friends':
        names.append(f'{name} ({film})')
    return list(dict.fromkeys(names))[:5]


def lookup_page_image(title: str, *, pause: float) -> dict | None:
    body = api_get({
        'action': 'query', 'titles': title, 'prop': 'pageimages',
        'piprop': 'thumbnail|original', 'pithumbsize': '650',
    }, pause=pause)
    for page in body.get('query', {}).get('pages', []):
        if page.get('missing') or not page.get('pageid'):
            continue
        thumb = page.get('thumbnail') or page.get('original') or {}
        src = thumb.get('source')
        if src and str(src).startswith('https://static.wikia.nocookie.net/'):
            return {'title': page.get('title', title), 'pageid': int(page['pageid']), 'src': src}
        # Some wikis do not enable pageimages. In that case, look for a
        # character-named file on the article rather than trusting its first image.
        try:
            imglist = api_get({'action': 'query', 'titles': page['title'],
                               'prop': 'images', 'imlimit': '40'}, pause=pause)
            files = [x['title'] for p in imglist.get('query', {}).get('pages', [])
                     for x in p.get('images', []) if x.get('title', '').startswith('File:')]
            core_name = core.normalized(title)
            candidates = sorted((f for f in files if core_name and core_name in core.normalized(f)),
                                key=len)[:3]
            if candidates:
                info = api_get({'action': 'query', 'titles': '|'.join(candidates),
                                'prop': 'imageinfo', 'iiprop': 'url'}, pause=pause)
                for filepage in info.get('query', {}).get('pages', []):
                    for row in filepage.get('imageinfo', []):
                        image_url = row.get('url', '')
                        if image_url.startswith('https://static.wikia.nocookie.net/'):
                            return {'title': page['title'], 'pageid': int(page['pageid']), 'src': image_url}
        except (HTTPError, URLError, OSError, ValueError):
            pass
    return None


def search_page_titles(name: str, film: str, *, pause: float) -> list[str]:
    # Search is a fallback: name + movie avoids many homonyms.
    query = ' '.join(s for s in [name, film] if s and s != 'Mickey & Friends')
    body = api_get({'action': 'query', 'list': 'search', 'srsearch': query, 'srlimit': '5'}, pause=pause)
    return [row['title'] for row in body.get('query', {}).get('search', []) if row.get('title')]


def find_wiki_images(target: dict, *, pause: float, max_candidates: int = 2) -> list[dict]:
    seen = set()
    found = []
    film = (target.get('films') or [''])[0]
    # Exact pages first, then alternative names and contextual search.
    for title in suggest_page_titles(target):
        try:
            item = lookup_page_image(title, pause=pause)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            if isinstance(exc, (HTTPError, URLError, TimeoutError)):
                # Network restrictions affect the whole API. Surface them to
                # the caller so it can stop, rather than repeatedly timing out.
                raise
            continue
        if item and item['src'] not in seen:
            found.append(item)
            seen.add(item['src'])
        if len(found) >= max_candidates:
            return found
    try:
        more_titles = search_page_titles(target['name'], film, pause=pause)
        for title in more_titles[:3]:
            item = lookup_page_image(title, pause=pause)
            if item and item['src'] not in seen:
                found.append(item)
                seen.add(item['src'])
            if len(found) >= max_candidates:
                break
    except (HTTPError, URLError, OSError, ValueError):
        pass
    return found


def candidate_entry(target: dict, item: dict, seq: int) -> dict:
    img, dimensions = core.try_image_url(item['src'])
    basename = f'{core.safe_id(target["id"])}--wiki-{item["pageid"]}-{seq}.webp'
    rel = 'images/new-candidates/' + basename
    output = ROOT / rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(img)
    return {
        'path': rel, 'apiId': None, 'apiName': item['title'], 'apiImageUrl': item['src'],
        'sourceUrl': wiki_page(item['title']), 'filmMatch': False,
        'width': dimensions[0], 'height': dimensions[1],
        'sha256': hashlib.sha256(img).hexdigest(), 'publishedPath': '',
        'reviewRequired': True, 'searchProvider': 'Disney Wiki (unverified)',
    }


def add_manual_seeds(target_map: dict, manifest: dict, index: dict) -> int:
    if not SEED_MAP.is_file():
        return 0
    try:
        seeds = core.read_json(SEED_MAP)
    except Exception as exc:
        raise ValueError('Invalid manual-provided/seed-metadata.json') from exc
    total = 0
    for seed in seeds:
        cid = str(seed.get('characterId', ''))
        filename = str(seed.get('filename', ''))
        if cid not in target_map or manifest.get(cid, {}).get('reviewed'):
            continue
        if not re.fullmatch(r'[a-zA-Z0-9_-]+\.png', filename):
            raise ValueError('Unsafe seed filename')
        source = (SEEDS / filename)
        if not source.is_file():
            raise FileNotFoundError(f'Missing {source}')
        converted, size = core.convert_image(source.read_bytes())
        rel = f'images/new-candidates/{core.safe_id(cid)}--user-reference.webp'
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(converted)
        old = index.setdefault(cid, {'status': 'NEEDS_REVIEW', 'candidates': []})
        candidates = old.setdefault('candidates', [])
        if not any(x.get('path') == rel for x in candidates):
            candidates.append({
                'path': rel, 'apiId': None, 'apiName': seed.get('label', target_map[cid]['name']),
                'apiImageUrl': '', 'sourceUrl': '', 'filmMatch': False,
                'width': size[0], 'height': size[1],
                'sha256': hashlib.sha256(converted).hexdigest(),
                'publishedPath': '', 'reviewRequired': True,
                'searchProvider': 'User-supplied reference (rights unverified)',
            })
            total += 1
        if old.get('status') not in {'PUBLISHED'}:
            old['status'] = 'NEEDS_REVIEW'
    return total


def run(limit: int, pause: float):
    targets, manifest, container = core.load_data()
    index = container['characters']
    target_map = {x['id']: x for x in targets}
    before_manifest = MANIFEST.read_bytes()
    existing_paths = {p for v in index.values() for x in v.get('candidates', []) if (p := x.get('path'))}
    # User supplied singles can be added even if another source found a candidate.
    manual_count = add_manual_seeds(target_map, manifest, index)
    eligible = [x for x in targets if not manifest.get(x['id'], {}).get('reviewed')
                and not index.get(x['id'], {}).get('candidates')]
    if limit > 0:
        eligible = eligible[:limit]
    print('Already approved:', sum(bool(manifest.get(x['id'], {}).get('reviewed')) for x in targets))
    print('Previously indexed candidate paths:', len(existing_paths))
    print('Added user-provided image candidates:', manual_count)
    print('Trying Disney Wiki API for characters with zero candidates:', len(eligible))
    fetched = failed = requests_blocked = network_error_streak = 0
    errors = {}
    with REPORT.open('w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['characterId', '日本語名', 'English', '作品', '結果', '検索ページ', '画像検索'])
        for number, target in enumerate(eligible, start=1):
            cid = target['id']
            status = 'NOT_FOUND'
            try:
                pages = find_wiki_images(target, pause=pause)
                for seq, page in enumerate(pages, start=1):
                    try:
                        new = candidate_entry(target, page, seq)
                        cur = index.setdefault(cid, {'status': 'NEEDS_REVIEW', 'candidates': []})
                        if not any(x.get('path') == new['path'] for x in cur.setdefault('candidates', [])):
                            cur['candidates'].append(new)
                            fetched += 1
                            status = 'CANDIDATE_NEEDS_REVIEW'
                        cur['status'] = 'NEEDS_REVIEW'
                    except Exception as exc:
                        errors.setdefault(cid, []).append(str(exc)[:120])
                if not pages:
                    failed += 1
                network_error_streak = 0
            except HTTPError as exc:
                status = f'SOURCE_HTTP_{exc.code}'
                failed += 1
                network_error_streak += 1
                if exc.code in {401, 403, 429}:
                    requests_blocked += 1
            except (OSError, URLError, ValueError) as exc:
                status = 'SOURCE_UNAVAILABLE'
                failed += 1
                network_error_streak += 1
                errors.setdefault(cid, []).append(str(exc)[:120])
            writer.writerow([cid, target['jp'], target['name'], ' / '.join(target['films']), status,
                             wiki_page(target['name']), image_search_url(target['name'], target['films'][0])])
            if number % 20 == 0:
                print(f'Looked up {number}/{len(eligible)}, downloaded {fetched}, unavailable/no match {failed}', flush=True)
            # Don't hammer the same blocked API hundreds of times.
            if (requests_blocked >= 3 or network_error_streak >= 4) and fetched == 0:
                print('WARNING: Disney Wiki API appears unavailable; manual web search links remain available.', file=sys.stderr)
                break
    core.write_json(INDEX, container)
    core.generate_status(targets, manifest, container)
    if MANIFEST.read_bytes() != before_manifest:
        raise RuntimeError('Unexpected manifest modification')
    print('RESULT: Fallback images saved:', fetched, '| User reference images:', manual_count)
    print('Current reviewed manifest: UNCHANGED. Open review-new-images.html and approve only true single-character images.')
    if errors:
        print('Individual errors:', len(errors), '| First examples:', list(errors.items())[:3])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=0, help='0 = try all remaining new characters without candidates')
    parser.add_argument('--pause', type=float, default=0.35, help='Minimum delay between API requests')
    args = parser.parse_args()
    if args.limit < 0 or not 0 <= args.pause <= 5:
        parser.error('Invalid limit/pause')
    run(args.limit, args.pause)


if __name__ == '__main__':
    main()
