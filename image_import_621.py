#!/usr/bin/env python3
"""Fetch review candidates for the 366 new characters; publish ONLY user-approved files.

This script NEVER marks downloaded candidates as reviewed automatically.
It preserves all pre-existing entries in images/manifest.json.
Run from the root of mop626/disney via GitHub Actions or locally.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:
    raise SystemExit('Pillow is required: python -m pip install Pillow')

ROOT = Path(__file__).resolve().parent
TARGETS_FILE = ROOT / 'new_characters.json'
MANIFEST_FILE = ROOT / 'images' / 'manifest.json'
CANDIDATE_DIR = ROOT / 'images' / 'new-candidates'
INDEX_FILE = CANDIDATE_DIR / 'index.json'
DECISIONS_FILE = CANDIDATE_DIR / 'approvals.json'
REJECTED_FILE = ROOT / 'images' / 'audit' / 'rejections.json'
REPORT_FILE = CANDIDATE_DIR / 'status.csv'
API_BASE = 'https://api.disneyapi.dev/character'
HEADERS = {
    'User-Agent': 'MagicalCharacterQuiz/1.0 (non-commercial fan image candidates; manual review)',
    'Accept': '*/*',
}
ALLOWED_IMAGE_HOSTS = {
    'static.wikia.nocookie.net',
    'vignette.wikia.nocookie.net',
    'images.wikia.nocookie.net',
}
MAX_IMAGE_BYTES = 8_000_000
MAX_CANDIDATES_PER_CHAR = 2


def read_json(path: Path, default=None):
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(f'Missing {path.relative_to(ROOT)}. Upload existing site files first.')
    with path.open('r', encoding='utf-8') as file:
        return json.load(file)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def load_data():
    targets = read_json(TARGETS_FILE)
    if not isinstance(targets, list) or len(targets) != 366:
        raise ValueError('Expected exactly 366 new characters. Do not substitute an old list.')
    ids = [c['id'] for c in targets]
    if len(set(ids)) != len(ids) or not all(v.startswith('extended-') for v in ids):
        raise ValueError('new_characters.json has duplicate or invalid character IDs')
    live_data_file = ROOT / 'data.js'
    if live_data_file.is_file():
        raw = live_data_file.read_text(encoding='utf-8').split('=', 1)[1].strip().rstrip(';')
        live_ids = {record['id'] for record in json.loads(raw)}
        absent = [cid for cid in ids if cid not in live_ids]
        if absent:
            raise ValueError(f'{len(absent)} target character IDs not found in current data.js; do not import into mismatched version.')
    manifest = read_json(MANIFEST_FILE)
    if not isinstance(manifest, dict):
        raise ValueError('images/manifest.json must be an object')
    if len(manifest) < 100:
        print('WARNING: existing manifest contains fewer than 100 entries. Verify that you have the live repository.', file=sys.stderr)
    index = read_json(INDEX_FILE, {'version': 1, 'characters': {}})
    if not isinstance(index, dict) or not isinstance(index.get('characters'), dict):
        raise ValueError('images/new-candidates/index.json has an invalid structure')
    return targets, manifest, index


def normalized(text):
    value = unicodedata.normalize('NFKD', str(text or '')).casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r'\([^)]*\)', '', value)  # ignore e.g. (film) / (2021 film)
    value = value.replace('&', 'and')
    value = re.sub(r'\bii\b', '2', value)
    value = re.sub(r'\biii\b', '3', value)
    value = re.sub(r'[^a-z0-9]+', '', value)
    return value


def film_overlap(character, api_character):
    target_titles = {normalized(t) for t in character.get('films', []) if t}
    api_titles = {
        normalized(title)
        for field in ('films', 'shortFilms', 'tvShows')
        for title in (api_character.get(field) or [])
        if title
    }
    return bool(target_titles.intersection(api_titles))


def candidate_score(character, api_character):
    aliases = [character['name'], *(character.get('aliases') or [])]
    english_names = {normalized(t) for t in aliases if re.search('[A-Za-z]', str(t))}
    if not normalized(api_character.get('name', '')) in english_names:
        return 0
    # Same name + same film is preferred. Name-only matches are still REVIEW candidates.
    return 100 if film_overlap(character, api_character) else 50


def retrieve(url: str, *, max_bytes: int, retries: int = 3, image: bool = False):
    if urlparse(url).scheme != 'https':
        raise ValueError('HTTPS is required')
    if image and (urlparse(url).hostname or '').lower() not in ALLOWED_IMAGE_HOSTS:
        raise ValueError('External image host not on allowed list')
    last = None
    for attempt in range(retries):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=24) as response:
                final = response.geturl()
                if image and (urlparse(final).hostname or '').lower() not in ALLOWED_IMAGE_HOSTS:
                    raise ValueError('Image redirect to unexpected host')
                content_type = response.headers.get('Content-Type', '')
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError('Downloaded content is too large')
                return body, content_type
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(min(8, 2 ** attempt))
    raise last if last else RuntimeError('Download failed')


def get_api_characters(page_size: int = 100, max_pages: int = 160):
    results = []
    for page in range(1, max_pages + 1):
        url = f'{API_BASE}?page={page}&pageSize={page_size}'
        try:
            raw, _ = retrieve(url, max_bytes=2_000_000)
            body = json.loads(raw)
            rows = body.get('data') or []
            if isinstance(rows, dict):
                rows = [rows]
            if not isinstance(rows, list):
                raise ValueError('Unexpected Disney API response format')
            results.extend(rows)
            if page == 1:
                print('Disney API reports', body.get('info', {}).get('totalPages', '?'), 'pages.')
            if page % 20 == 0:
                print('Loaded API page', page, 'records', len(results), flush=True)
            total_pages = body.get('info', {}).get('totalPages')
            if not rows or (total_pages is not None and page >= int(total_pages)) or (total_pages is None and len(rows) < page_size):
                break
        except Exception as exc:
            print(f'WARNING: API page {page} failed: {str(exc)[:160]}. Stopping; partial results will be used.', file=sys.stderr)
            break
    return results


def safe_id(character_id):
    val = re.sub('[^a-zA-Z0-9_-]', '_', character_id)
    if not val or len(val) > 170:
        raise ValueError('Invalid or excessively long character ID')
    return val


def convert_image(data: bytes):
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.seek(0)
            im = ImageOps.exif_transpose(im)
            if im.width < 100 or im.height < 100 or im.width / im.height > 3.5 or im.height / im.width > 3.5:
                raise ValueError('Image too small or excessively elongated')
            im.thumbnail((700, 700), Image.Resampling.LANCZOS)
            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
            out = io.BytesIO()
            im.save(out, format='WEBP', quality=81, method=5)
            result = out.getvalue()
            if len(result) < 1500:
                raise ValueError('Image has unexpectedly little data')
            return result, im.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Not a readable character image') from exc


def try_image_url(url):
    options = [url]
    if '/revision/' in url:
        options.append(url.split('/revision/', 1)[0])
    for candidate in dict.fromkeys(options):
        try:
            content, mime = retrieve(candidate, max_bytes=MAX_IMAGE_BYTES, image=True)
            if not mime.lower().startswith('image/'):
                raise ValueError(f'Non-image response: {mime}')
            return convert_image(content)
        except Exception:
            continue
    raise ValueError('Image URL did not return a valid image; site may block automated access')


def fetch_task(character, api_item, score):
    api_id = str(api_item.get('_id', ''))
    if not api_id.isdecimal() or not api_item.get('imageUrl'):
        return character['id'], None, 'missing API id or image URL'
    filename = f'{safe_id(character["id"])}--{api_id}.webp'
    relpath = 'images/new-candidates/' + filename
    path = ROOT / relpath
    try:
        content, size = try_image_url(str(api_item['imageUrl']))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        entry = {
            'path': relpath,
            'apiId': int(api_id),
            'apiName': str(api_item.get('name', '')),
            'apiImageUrl': str(api_item['imageUrl']),
            'sourceUrl': str(api_item.get('sourceUrl') or ''),
            'filmMatch': bool(score == 100),
            'width': size[0], 'height': size[1],
            'sha256': hashlib.sha256(content).hexdigest(),
            'publishedPath': '',
        }
        return character['id'], entry, ''
    except Exception as exc:
        return character['id'], None, str(exc)[:160]


def generate_status(targets, manifest, index):
    target_map = {x['id']: x for x in targets}
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    with REPORT_FILE.open('w', encoding='utf-8-sig', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['characterId', '日本語名', 'English', '作品', '画像候補数', '公開済み', '備考'])
        for cid, c in target_map.items():
            item = index['characters'].get(cid, {})
            count = len(item.get('candidates') or [])
            writer.writerow([cid, c['jp'], c['name'], ' / '.join(c['films']), count,
                             'yes' if cid in manifest and manifest[cid].get('reviewed') else 'no',
                             item.get('status', '')])


def fetch_images(*, limit: int, workers: int, max_pages: int):
    targets, manifest, index = load_data()
    candidate_index = index['characters']
    items = [x for x in targets if x['id'] not in manifest or manifest[x['id']].get('reviewed') is not True]
    items = [x for x in items if not any((ROOT / y['path']).exists() for y in candidate_index.get(x['id'], {}).get('candidates', []))]
    if limit > 0:
        items = items[:limit]
    print('New characters:', len(targets), '| Need fetch:', len(items), '| Existing manifest:', len(manifest))
    if not items:
        generate_status(targets, manifest, index)
        print('Nothing to download. Existing approved entries unchanged.')
        return
    api_rows = get_api_characters(max_pages=max_pages)
    if not api_rows:
        raise RuntimeError('Disney API returned no characters. No files were changed.')
    by_name = defaultdict(list)
    for row in api_rows:
        if isinstance(row, dict) and row.get('imageUrl') and row.get('name'):
            by_name[normalized(row['name'])].append(row)
    futures = []
    attempted = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for character in items:
            matching = []
            english = [character['name']] + [s for s in character.get('aliases', []) if re.search('[A-Za-z]', str(s))]
            matching_ids = set()
            for name in english:
                for row in by_name.get(normalized(name), []):
                    score = candidate_score(character, row)
                    if score > 0 and str(row.get('_id')) not in matching_ids:
                        matching.append((score, row))
                        matching_ids.add(str(row.get('_id')))
            matching.sort(key=lambda match: (-match[0], str(match[1].get('_id'))))
            if not matching:
                candidate_index[character['id']] = {'status': 'NO_EXACT_API_MATCH', 'candidates': []}
                continue
            candidate_index[character['id']] = {'status': 'NEEDS_REVIEW', 'candidates': []}
            for score, row in matching[:MAX_CANDIDATES_PER_CHAR]:
                futures.append(pool.submit(fetch_task, character, row, score))
                attempted += 1
        downloaded = 0
        for i, f in enumerate(as_completed(futures), start=1):
            cid, entry, failure = f.result()
            if entry:
                candidate_index[cid]['candidates'].append(entry)
                downloaded += 1
            else:
                candidate_index[cid]['errors'] = (candidate_index[cid].get('errors') or []) + [failure]
            if i % 30 == 0:
                print(f'Image attempts {i}/{attempted}; saved {downloaded}', flush=True)
        for character in items:
            item = candidate_index.get(character['id'])
            if item and item.get('status') == 'NEEDS_REVIEW' and not item['candidates']:
                item['status'] = 'IMAGE_DOWNLOAD_FAILED'
    write_json(INDEX_FILE, index)
    if not DECISIONS_FILE.exists():
        write_json(DECISIONS_FILE, {'version': 1, 'approved': []})
    generate_status(targets, manifest, index)
    ready = sum(bool(v.get('candidates')) for v in candidate_index.values())
    print(f'Done: {downloaded} candidate images saved, for {ready} unique characters. Existing approved manifest unchanged.')
    print('Review at https://mop626.github.io/disney/review-new-images.html')


def publish_approvals():
    targets, manifest, index = load_data()
    allowed_targets = {c['id'] for c in targets}
    decisions = read_json(DECISIONS_FILE)
    rejected_data = read_json(REJECTED_FILE, {'version': 1, 'rejected': []})
    blocked_candidates = {(x.get('characterId'), x.get('path')) for x in rejected_data.get('rejected', [])}
    if decisions.get('version') != 1 or not isinstance(decisions.get('approved'), list):
        raise ValueError('Invalid approvals.json schema')
    seen = set()
    promoted = 0
    errors = []
    for approval in decisions['approved']:
        if not isinstance(approval, dict):
            errors.append('Malformed approval item')
            continue
        cid, candidate_path = approval.get('characterId'), approval.get('path')
        if cid not in allowed_targets or cid in seen:
            errors.append(f'{cid}: invalid or duplicate character ID')
            continue
        if (cid, candidate_path) in blocked_candidates:
            errors.append(f'{cid}: this candidate was rejected by image quality review; cannot publish')
            continue
        seen.add(cid)
        if cid in manifest:
            if manifest[cid].get('reviewed') is True:
                continue  # Do not replace any previously reviewed image.
            errors.append(f'{cid}: existing unapproved manifest entry, manual inspection required')
            continue
        candidate_item = index['characters'].get(cid, {})
        found = next((x for x in candidate_item.get('candidates', []) if x.get('path') == candidate_path), None)
        if not found:
            errors.append(f'{cid}: chosen candidate is not listed in the downloader index')
            continue
        if not isinstance(candidate_path, str) or not re.fullmatch(r'images/new-candidates/[A-Za-z0-9_-]+\.webp', candidate_path):
            errors.append(f'{cid}: bad candidate path')
            continue
        source = ROOT / candidate_path
        if not source.is_file():
            errors.append(f'{cid}: candidate image file missing')
            continue
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != found.get('sha256'):
            errors.append(f'{cid}: candidate image file changed; must review again')
            continue
        # Validate image before copying to the production image namespace.
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
        except Exception:
            errors.append(f'{cid}: corrupted image')
            continue
        dest_relative = f'images/{safe_id(cid)}.webp'
        dest = ROOT / dest_relative
        if dest.exists():
            errors.append(f'{cid}: production image file already exists; will not overwrite')
            continue
        shutil.copyfile(source, dest)
        manifest[cid] = {
            'path': dest_relative, 'reviewed': True,
            'singleCharacter': True, 'characterId': cid,
        }
        found['publishedPath'] = dest_relative
        candidate_item['status'] = 'PUBLISHED'
        promoted += 1
    if promoted:
        write_json(MANIFEST_FILE, manifest)
        write_json(INDEX_FILE, index)
    generate_status(targets, manifest, index)
    print('Published newly approved images:', promoted, '| Existing originals preserved:', len(manifest) - promoted)
    if errors:
        print('Skipped:', len(errors))
        for e in errors[:30]:
            print(' -', e)
        if promoted == 0:
            raise RuntimeError('No images published; see skipped reasons')


def print_status():
    targets, manifest, index = load_data()
    approved = sum(bool(manifest.get(c['id'], {}).get('reviewed')) for c in targets)
    with_images = sum(bool(index['characters'].get(c['id'], {}).get('candidates')) for c in targets)
    print('Added characters total: ', len(targets))
    print('Image candidates found: ', with_images)
    print('Manually approved images:', approved)
    print('Still missing images:  ', len(targets) - approved)
    generate_status(targets, manifest, index)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('operation', choices=['fetch', 'publish', 'status'])
    cli.add_argument('--limit', type=int, default=0, help='Maximum new characters to attempt. 0 means all.')
    cli.add_argument('--workers', type=int, default=4)
    cli.add_argument('--max-pages', type=int, default=160)
    args = cli.parse_args()
    if args.limit < 0 or not 1 <= args.workers <= 8 or args.max_pages < 1:
        cli.error('Invalid --limit, --workers or --max-pages')
    if args.operation == 'fetch':
        fetch_images(limit=args.limit, workers=args.workers, max_pages=args.max_pages)
    elif args.operation == 'publish':
        publish_approvals()
    else:
        print_status()


if __name__ == '__main__':
    main()
