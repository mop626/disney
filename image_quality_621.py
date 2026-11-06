#!/usr/bin/env python3
"""Review-gated image quality repair for the 621-character Disney quiz.

Run at the repository root. This tool does NOT infer character identity from an image.
Changes only follow explicitly reviewed decisions.json; wrong Te Ka *candidates* are
blocked by a separate reject list without touching any other approved images.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / 'images' / 'manifest.json'
INDEX_PATH = ROOT / 'images' / 'new-candidates' / 'index.json'
APPROVALS_PATH = ROOT / 'images' / 'new-candidates' / 'approvals.json'
DECISIONS_PATH = ROOT / 'images' / 'audit' / 'decisions.json'
REJECTIONS_PATH = ROOT / 'images' / 'audit' / 'rejections.json'
HISTORY_PATH = ROOT / 'images' / 'audit' / 'fix-history.json'
REPORT_PATH = ROOT / 'images' / 'audit' / 'report.json'
MISSING_CSV_PATH = ROOT / 'images' / 'audit' / 'missing-characters.csv'
DATA_PATH = ROOT / 'data.js'

CANDIDATE_PATTERN = re.compile(r'^images/new-candidates/[A-Za-z0-9_-]+\.webp$')
MANUAL_PATTERN = re.compile(r'^images/manual/[A-Za-z0-9_-]+\.webp$')
SOURCE_PATTERN = re.compile(r'^images/[A-Za-z0-9_-]+\.(?:webp|png|jpg|jpeg)$')
REASONS = {'wrong_character', 'multiple_characters', 'poor_image', 'other', 'new_image'}
MAX_FILE = 8 * 1024 * 1024


def read_json(path: Path, *, default=None):
    if not path.exists():
        if default is None:
            raise ValueError(f'Missing required file: {path.relative_to(ROOT)}')
        return copy.deepcopy(default)
    with path.open('r', encoding='utf8') as f:
        return json.load(f)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    output = path.with_suffix(path.suffix + '.tmp')
    output.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    output.replace(path)


def catalog():
    text = DATA_PATH.read_text('utf8').strip()
    # data.js contains only a JSON literal exported as `export const curated = [...]`.
    match = re.fullmatch(r'export\s+const\s+curated\s*=\s*(\[.*\])\s*;?\s*', text, re.DOTALL)
    if not match:
        raise ValueError('data.js is not the expected exported JSON array')
    rows = json.loads(match.group(1))
    if not isinstance(rows, list) or len(rows) < 500:
        raise ValueError('Wrong catalog: expected at least 500 characters')
    ids = [r.get('id') for r in rows]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Duplicate/invalid character IDs')
    return {r['id']: r for r in rows}


def safe_id(id_: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_-]', '_', id_)
    if not value or len(value) > 170:
        raise ValueError('Bad character ID for filename')
    return value


def valid_image(path: Path):
    if not path.exists() or not path.is_file():
        raise ValueError(f'Image not found: {path.relative_to(ROOT)}')
    if path.stat().st_size > MAX_FILE or path.stat().st_size < 500:
        raise ValueError(f'Image has suspicious size: {path.relative_to(ROOT)}')
    try:
        with Image.open(path) as img:
            width, height = img.size
            file_format = img.format
            img.verify()
        if width < 100 or height < 100 or width / height > 3.5 or height / width > 3.5:
            raise ValueError('Image dimensions unsuitable for quiz')
        if file_format not in {'WEBP', 'PNG', 'JPEG'}:
            raise ValueError('Unsupported image format')
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError(f'Corrupted image: {path.relative_to(ROOT)}') from e


def load_state():
    cat = catalog()
    manifest = read_json(MANIFEST_PATH)
    index = read_json(INDEX_PATH)
    approvals = read_json(APPROVALS_PATH, default={'version': 1, 'approved': []})
    decisions = read_json(DECISIONS_PATH, default={'version': 1, 'confirmManualReview': False, 'updates': [], 'rejectCandidates': []})
    rejected = read_json(REJECTIONS_PATH, default={'version': 1, 'rejected': []})
    history = read_json(HISTORY_PATH, default={'version': 1, 'changes': []})
    if not isinstance(manifest, dict) or not isinstance(index, dict) or not isinstance(index.get('characters'), dict):
        raise ValueError('Invalid manifest or candidate index')
    if not isinstance(approvals, dict) or approvals.get('version') != 1 or not isinstance(approvals.get('approved'), list):
        raise ValueError('Invalid approvals.json')
    if not isinstance(decisions, dict) or decisions.get('version') != 1 or not isinstance(decisions.get('updates'), list) or not isinstance(decisions.get('rejectCandidates'), list):
        raise ValueError('Invalid decisions.json')
    if not isinstance(rejected, dict) or rejected.get('version') != 1 or not isinstance(rejected.get('rejected'), list):
        raise ValueError('Invalid rejections.json')
    if not isinstance(history, dict) or not isinstance(history.get('changes'), list):
        raise ValueError('Invalid fix-history.json')
    return cat, manifest, index, approvals, decisions, rejected, history


def rejected_set(rejected):
    out = set()
    for item in rejected['rejected']:
        cid, path = item.get('characterId'), item.get('path')
        if not isinstance(cid, str) or not isinstance(path, str) or not CANDIDATE_PATTERN.fullmatch(path):
            raise ValueError('Invalid rejected candidate record')
        out.add((cid, path))
    return out


def get_candidate(index, cid, source):
    if not CANDIDATE_PATTERN.fullmatch(source):
        raise ValueError(f'{cid}: Invalid candidate path')
    for candidate in index['characters'].get(cid, {}).get('candidates', []):
        if candidate.get('path') == source:
            return candidate
    raise ValueError(f'{cid}: candidate is not in image index: {source}')


def source_bytes(index, cid, candidate_path, manual_path, rejected):
    if bool(candidate_path) == bool(manual_path):
        raise ValueError(f'{cid}: select exactly one source (candidatePath or manualPath)')
    if candidate_path:
        if (cid, candidate_path) in rejected:
            raise ValueError(f'{cid}: rejected candidate cannot be published')
        record = get_candidate(index, cid, candidate_path)
        src = ROOT / candidate_path
        valid_image(src)
        content = src.read_bytes()
        if hashlib.sha256(content).hexdigest() != record.get('sha256'):
            raise ValueError(f'{cid}: candidate hash changed since review')
        return content, candidate_path
    expected = f'images/manual/{safe_id(cid)}.webp'
    if not isinstance(manual_path, str) or not MANUAL_PATTERN.fullmatch(manual_path) or manual_path != expected:
        raise ValueError(f'{cid}: invalid manual image location; required {expected}')
    src = ROOT / manual_path
    valid_image(src)
    content = src.read_bytes()
    with Image.open(io.BytesIO(content)) as im:
        if im.format != 'WEBP':
            raise ValueError('Manual image must be a real WebP file, not renamed JPEG')
    return content, manual_path


def normalize_name(s):
    import unicodedata
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s).lower()).encode('ascii', 'ignore').decode())


def report_for(cat, manifest, index, rejected):
    rej = rejected_set(rejected)
    sha_to_char = defaultdict(list)
    for cid, data in index['characters'].items():
        if cid not in manifest:
            continue
        for can in data.get('candidates', []):
            if can.get('publishedPath') == manifest[cid].get('path') and can.get('sha256'):
                sha_to_char[can['sha256']].append(cid)
    issues = []
    total_published = 0
    for cid, ch in cat.items():
        m = manifest.get(cid)
        if not (isinstance(m, dict) and m.get('reviewed') is True and m.get('singleCharacter') is True and m.get('characterId') == cid and SOURCE_PATTERN.fullmatch(str(m.get('path', '')))):
            issues.append({'characterId': cid, 'type': 'missing', 'message': '画像未登録'})
            continue
        total_published += 1
        path = ROOT / m['path']
        if not path.is_file():
            issues.append({'characterId': cid, 'type': 'broken', 'message': '画像ファイルが見つかりません'})
        if cid in {'extended-mickey-friends-magica-de-spell', 'extended-the-lion-king-shenzi'}:
            issues.append({'characterId': cid, 'type': 'check', 'message': '過去に複数キャラ画像の指摘あり：現在画像を要確認'})
        row = index['characters'].get(cid, {})
        for can in row.get('candidates', []):
            if can.get('publishedPath') != m['path']:
                continue
            a = normalize_name(can.get('apiName', ''))
            english = {normalize_name(n) for n in [ch['name'], *(ch.get('aliases') or [])] if n}
            if a and a not in english and not any(a == x + 'gallery' for x in english):
                issues.append({'characterId': cid, 'type': 'check', 'message': '候補の画像元名がキャラクター名と異なります（目視確認）'})
            if len(set(sha_to_char.get(can.get('sha256'), []))) >= 2:
                issues.append({'characterId': cid, 'type': 'duplicate', 'message': '別キャラクターと同一の画像が使われています'})
    return {
        'version': 1,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'catalog': len(cat), 'imageRegistered': total_published,
        'missing': len(cat) - total_published,
        'rejectedCandidates': len(rej), 'issues': issues,
        'note': '要確認フラグはメタデータの疑いです。画像の人物数や本人確認は人の目で行ってください。',
    }


def write_missing_csv(cat, manifest):
    """Generate a human-readable list without touching production images."""
    MISSING_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MISSING_CSV_PATH.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['characterId', '日本語名', 'English', '作品', '画像検索'])
        for cid, row in cat.items():
            entry = manifest.get(cid)
            if isinstance(entry, dict) and entry.get('reviewed') is True and entry.get('singleCharacter') is True:
                continue
            film = ' / '.join(row.get('films') or [])
            link = 'https://www.google.com/search?' + urlencode({
                'tbm': 'isch', 'q': f'Disney {film} {row.get("name", "")} character solo image'})
            writer.writerow([cid, row.get('jp', ''), row.get('name', ''), film, link])


def apply_changes():
    cat, manifest, index, approvals, decisions, rejected, history = load_state()
    # No changes are performed if the review export is missing its explicit confirmation.
    updates = decisions['updates']
    rejects = decisions['rejectCandidates']
    if (updates or rejects) and decisions.get('confirmManualReview') is not True:
        raise ValueError('confirmManualReview:true is required for image changes')
    now = datetime.now(timezone.utc).isoformat()
    rejset = rejected_set(rejected)
    rejection_records = copy.deepcopy(rejected['rejected'])
    for record in rejects:
        if not isinstance(record, dict):
            raise ValueError('Invalid reject item')
        cid, path, reason = record.get('characterId'), record.get('path'), record.get('reason')
        if cid not in cat or reason not in REASONS:
            raise ValueError('Invalid rejected character or reason')
        get_candidate(index, cid, path)
        if (cid, path) not in rejset:
            rejection_records.append({'characterId': cid, 'path': path, 'reason': reason})
            rejset.add((cid, path))
    seen = set()
    planned_copies = {}
    applied = []
    new_manifest = copy.deepcopy(manifest)
    new_index = copy.deepcopy(index)
    new_approvals = copy.deepcopy(approvals)
    new_history = copy.deepcopy(history)
    for record in updates:
        if not isinstance(record, dict):
            raise ValueError('Malformed image update')
        cid = record.get('characterId')
        action = record.get('action')
        reason = record.get('reason')
        expected = record.get('expectedPath')
        if cid not in cat or cid in seen or action not in {'remove', 'replace', 'add'} or reason not in REASONS or not isinstance(expected, str):
            raise ValueError(f'Invalid/duplicate image decision for {cid}')
        seen.add(cid)
        old_entry = new_manifest.get(cid)
        old_path = old_entry.get('path', '') if isinstance(old_entry, dict) else ''
        if expected != old_path:
            raise ValueError(f'{cid}: manifest changed since review (expected {expected!r}, current {old_path!r})')
        if action == 'add' and old_entry:
            raise ValueError(f'{cid}: already has an image; use replace')
        if action in {'replace', 'remove'} and (not old_entry or not old_entry.get('reviewed')):
            raise ValueError(f'{cid}: no approved image to replace/remove')
        if action != 'remove':
            data, source = source_bytes(index, cid, record.get('candidatePath'), record.get('manualPath'), rejset)
            sha = hashlib.sha256(data).hexdigest()
            dest = f'images/fixed-{safe_id(cid)}-{sha[:12]}.webp'
            output = ROOT / dest
            if output.exists() and hashlib.sha256(output.read_bytes()).hexdigest() != sha:
                raise ValueError('Refusing to overwrite existing different image')
            planned_copies[dest] = data
            new_manifest[cid] = {'path': dest, 'reviewed': True, 'singleCharacter': True, 'characterId': cid}
            idx_rec = new_index['characters'].setdefault(cid, {'status': 'PUBLISHED', 'candidates': []})
            for candidate in idx_rec.get('candidates', []):
                if candidate.get('publishedPath') == old_path:
                    candidate['publishedPath'] = ''
                if candidate.get('path') == source:
                    candidate['publishedPath'] = dest
            idx_rec['status'] = 'PUBLISHED'
            if record.get('candidatePath'):
                # The reviewer said the old image is bad, not the alternative.
                pass
        else:
            dest = ''
            source = ''
            new_manifest.pop(cid, None)
            idx_rec = new_index['characters'].get(cid)
            if idx_rec:
                idx_rec['status'] = 'REQUIRES_NEW_IMAGE'
                for candidate in idx_rec.get('candidates', []):
                    if candidate.get('publishedPath') == old_path:
                        candidate['publishedPath'] = ''
        if action in {'remove', 'replace'}:
            # Prevent the old importer from re-publishing an invalid image later.
            new_approvals['approved'] = [p for p in new_approvals['approved'] if p.get('characterId') != cid]
            for candidate in index['characters'].get(cid, {}).get('candidates', []):
                if candidate.get('publishedPath') == old_path and candidate.get('path') and (cid, candidate['path']) not in rejset:
                    rejection_records.append({'characterId': cid, 'path': candidate['path'], 'reason': reason})
                    rejset.add((cid, candidate['path']))
        applied.append({'characterId': cid, 'action': action, 'reason': reason,
                        'oldPath': old_path, 'newPath': dest, 'source': source, 'at': now})
    # If already approved yet newly rejected, remove pending old approvals too.
    new_approvals['approved'] = [p for p in new_approvals['approved'] if (p.get('characterId'), p.get('path')) not in rejset]
    # Verify that no newly published image refers to a rejected path.
    new_history['changes'].extend(applied)
    # All input validation occurs BEFORE writing any output.
    for rel, raw in planned_copies.items():
        location = ROOT / rel
        location.parent.mkdir(parents=True, exist_ok=True)
        if not location.exists():
            location.write_bytes(raw)
    write_json(MANIFEST_PATH, new_manifest)
    write_json(INDEX_PATH, new_index)
    write_json(APPROVALS_PATH, new_approvals)
    write_json(REJECTIONS_PATH, {'version': 1, 'rejected': rejection_records})
    if applied:
        write_json(HISTORY_PATH, new_history)
    if updates or rejects:
        # Avoid reapplying stale decisions after the workflow has committed them.
        write_json(DECISIONS_PATH, {'version': 1, 'confirmManualReview': False, 'updates': [], 'rejectCandidates': []})
    write_json(REPORT_PATH, report_for(cat, new_manifest, new_index, {'rejected': rejection_records}))
    write_missing_csv(cat, new_manifest)
    print(f'Quality repair: {len(applied)} decisions applied; {len(rejection_records)} blocked candidates; published count: {len(new_manifest)}')
    print('Removed images are kept on disk for rollback. Only manifest paths change.')


def inspect():
    cat, manifest, index, approvals, decisions, rejected, history = load_state()
    report = report_for(cat, manifest, index, rejected)
    write_json(REPORT_PATH, report)
    write_missing_csv(cat, manifest)
    print('Catalog:', report['catalog'], '| Images:', report['imageRegistered'], '| Missing:', report['missing'])
    print('Potential metadata issues:', sum(x['type'] == 'check' for x in report['issues']))
    print('This does not verify the characters visually. Open image-quality-review.html for manual QA.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect', 'apply'])
    args = parser.parse_args()
    if args.mode == 'inspect':
        inspect()
    else:
        apply_changes()
