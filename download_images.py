"""Download images from Disney API to GitHub Pages repository. Verify image rights before publishing."""
import json,re,time,urllib.request,urllib.parse, pathlib, mimetypes
root=pathlib.Path(__file__).resolve().parent
src=(root/'data.js').read_text(encoding='utf-8')
characters=json.loads(src.split('=',1)[1].strip().rstrip(';'))
manifest=json.loads((root/'images/manifest.json').read_text())
byname={c['name'].casefold():c for c in characters}
headers={'User-Agent':'MagicalCharacterQuiz/1.1 (personal educational quiz)'}
def get(url):
 req=urllib.request.Request(url,headers=headers)
 with urllib.request.urlopen(req,timeout=22) as r:return r.read(),r.headers.get('Content-Type','')
found=0
for page in range(1,161):
 try:
  body,_=get(f'https://api.disneyapi.dev/character?page={page}&pageSize=100')
  response=json.loads(body)
 except Exception as e:
  print('API error',page,e)
  if page==1:break
  continue
 for entry in response.get('data',[]):
  c=byname.get(str(entry.get('name','')).casefold())
  if not c or c['id'] in manifest or not entry.get('imageUrl'):continue
  try:
   image,ctype=get(entry['imageUrl'])
   if not ctype.startswith('image/') or len(image)<2000 or len(image)>8_000_000:continue
   ext='.png' if 'png' in ctype else '.webp' if 'webp' in ctype else '.jpg'
   fname=re.sub('[^a-zA-Z0-9_-]','_',c['id'])+ext
   (root/'images'/fname).write_bytes(image)
   manifest[c['id']]='images/'+fname
   found+=1
   if found%10==0:print('Downloaded',found)
  except Exception as e:print('Image failed:',c['name'],str(e)[:90])
 if page>=int(response.get('info',{}).get('totalPages',page)):break
 (root/'images/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
(root/'images/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('Images downloaded:',found,'Total:',len(manifest))
