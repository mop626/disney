"""Download review candidates only; never change the approved manifest."""
import json, pathlib, re, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'MagicalCharacterQuiz/2.0'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read(8_000_001), response.headers.get('Content-Type', '')

def matches(character, entry):
    titles = {str(t).casefold() for key in ('films', 'tvShows', 'shortFilms') for t in (entry.get(key) or [])}
    return character['name'].casefold() == str(entry.get('name', '')).strip().casefold() and bool(titles & {t.casefold() for t in character['films']})

def main():
    src = (ROOT / 'data.js').read_text(encoding='utf-8')
    characters = json.loads(src.split('=', 1)[1].strip().rstrip(';'))
    approved = json.loads((ROOT / 'images/manifest.json').read_text(encoding='utf-8'))
    pending = ROOT / 'images/candidates'
    pending.mkdir(parents=True, exist_ok=True)
    entries = []
    for page in range(1, 161):
        body, _ = get(f'https://api.disneyapi.dev/character?page={page}&pageSize=100')
        response = json.loads(body)
        rows = response.get('data') or []
        if isinstance(rows, dict): rows = [rows]
        for entry in rows:
            for character in characters:
                if character['id'] in approved or not matches(character, entry) or not entry.get('imageUrl'): continue
                try:
                    image, content_type = get(entry['imageUrl'])
                    if not content_type.startswith('image/') or not 2000 <= len(image) <= 8_000_000: continue
                    ext = '.png' if 'png' in content_type else '.webp' if 'webp' in content_type else '.jpg'
                    filename = re.sub('[^a-zA-Z0-9_-]', '_', character['id'] + '-' + str(entry.get('_id'))) + ext
                    (pending / filename).write_bytes(image)
                    entries.append({'characterId': character['id'], 'name': character['name'], 'path': 'images/candidates/' + filename, 'apiId': entry.get('_id'), 'sourceUrl': entry.get('sourceUrl', ''), 'reviewed': False, 'singleCharacter': False})
                except Exception as error:
                    print('Candidate failed:', character['id'], str(error)[:120])
        (pending / 'index.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        if page >= int(response.get('info', {}).get('totalPages', page)): break
    print('Candidates:', len(entries), 'Approved manifest unchanged. Review manually before promotion.')

if __name__ == '__main__': main()
