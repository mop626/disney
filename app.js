import { curated } from './data.js?v=expanded-20261106';
const app=document.getElementById('app');
const STORE='magical-character-quiz-v1';
const state={view:'home',catalog:[],ready:0,total:0,loading:true,error:'',mode:null,deck:[],pos:0,answer:'',feedback:null,records:[],workSearch:'',workPage:0,sourceFilter:'all',difficulty:1};
const save=()=>{try{localStorage.setItem(STORE,JSON.stringify({wrong:history.wrong,bests:history.bests}))}catch{}};
let history={wrong:{},bests:[]};try{history={...history,...JSON.parse(localStorage.getItem(STORE)||'{}')}}catch{};
const escapeHTML=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=s=>String(s||'').normalize('NFKC').toLowerCase().replace(/[\s　・･._'’‐‑‒–—―-]/g,'').replace(/ー/g,'').replace(/[ァ-ヶ]/g,c=>String.fromCharCode(c.charCodeAt(0)-96));
const names=c=>[c.jp,c.name,...(c.aliases||[])].filter(Boolean).map(norm);
function isCorrect(guess,c){const g=norm(guess);return !!g&&names(c).includes(g);}
const random=a=>{let b=[...a];for(let i=b.length-1;i>0;i--){let j=Math.floor(Math.random()*(i+1));[b[i],b[j]]=[b[j],b[i]]}return b};
const getPlayable=()=>state.catalog.filter(c=>c.imageReviewed&&c.imageUrl&&c.imageOk!==false&&c.films.length);
const getTextPlayable=()=>state.catalog.filter(c=>typeof c.hint==='string'&&c.hint.trim()&&c.films.length);
function createCatalog(manifest={}){
 state.catalog=curated.map(c=>{const m=manifest[c.id];const path=m?.path;
 const approved=m?.reviewed===true&&m?.singleCharacter===true&&m?.characterId===c.id&&typeof path==='string'&&/^images\/[a-zA-Z0-9_-]+\.(webp|png|jpg|jpeg)$/.test(path);
 return {...c,imageUrl:approved?path:'',imageReviewed:approved,imageOk:undefined};});
 state.ready=getPlayable().length;
}
const button=(label,action,cl='')=>`<button class="button ${cl}" data-action="${action}">${label}</button>`;
const header=()=>`<header class="topbar"><button class="topbtn brand" data-action="home">✦ <span>MAGICAL</span> CHARACTER QUIZ</button><span class="pill">非公式ファンサイト</span></header>`;
const status=()=>`<div class="pills"><span class="pill">✦ 登録 ${state.catalog.length.toLocaleString('ja-JP')} キャラ</span><span class="pill">✧ 画像付き ${getPlayable().length.toLocaleString('ja-JP')} キャラ</span><span class="pill">📖 文字ヒント ${getTextPlayable().length.toLocaleString('ja-JP')} キャラ</span><span class="pill">🎬 ${new Set(state.catalog.flatMap(c=>c.films)).size} 作品・シリーズ</span><span class="pill">${state.loading?'☾ 画像一覧を確認中…':state.error?'△ 画像一覧は未取得':'✓ 画像は確認済みのみ出題'}</span></div>${state.error?`<div class="toast">${escapeHTML(state.error)}</div>`:''}`;
function home(){return `<div class="hero"><div class="moon">☾ ✧</div><div class="eyebrow">A LITTLE SPARKLE OF MAGIC</div><h1>まほうの<br><span>キャラクター検定</span></h1><p>その顔、名前まで覚えてる？<br>ディズニー＆ピクサーの仲間たちと、魔法のクイズの旅へ。</p>${status()}</div><div class="section-title"><h2>✦ あそび方を選ぼう</h2></div><div class="modes"><button class="mode" data-action="levels"><div class="emoji">🏰</div><h3>難易度別チャレンジ</h3><p>初級から超上級まで、最大20問の検定に挑戦</p><b>4つのレベル →</b></button><button class="mode" data-action="works"><div class="emoji">🎬</div><h3>作品別チャレンジ</h3><p>お気に入りの映画やシリーズから出題</p><b>作品を選ぶ →</b></button><button class="mode" data-action="random"><div class="emoji">✨</div><h3>ランダム出題</h3><p>50問・100問・無限モードで腕試し</p><b>自由にあそぶ →</b></button><button class="mode" data-action="text"><div class="emoji">📝</div><h3>文字ヒント検定</h3><p>新しく追加したキャラを、作品名とヒントで当てよう。画像なしでも遊べる！</p><b>20問・50問・100問・無限 →</b></button><button class="mode" data-action="review"><div class="emoji">💫</div><h3>復習の魔法</h3><p>間違えたキャラクターをもう一度覚えよう</p><b>${Object.keys(history.wrong||{}).length}キャラを復習 →</b></button></div>${history.bests.length?`<div class="panel"><b>✧ 最近の挑戦</b><p class="subtle small">${escapeHTML(history.bests[0]?.label||'')} — ${history.bests[0]?.score||0}/${history.bests[0]?.total||0} 正解</p></div>`:''}`}
const back=()=>`<button class="topbtn" data-action="home">← ホームに戻る</button>`;
function levels(){return `${back()}<div class="pagehead"><h1>🏰 難易度別チャレンジ</h1><p class="subtle">それぞれ最大20問。初級はおなじみのキャラクターから出題！</p></div><div class="levels">${[['🌟','初級','おなじみの人気キャラ',1],['🌙','中級','ちょっと詳しい人向け',2],['🔮','上級','記憶力が試される',3],['👑','超上級','マニアの領域に挑戦',4]].map(([e,t,d,n])=>`<button class="tile" data-level="${n}"><span class="icon">${e}</span><h3>${t}</h3><p>${d} · 最大20問</p><p class="count">画像あり ${getPlayable().filter(x=>x.difficulty===n).length}キャラ</p></button>`).join('')}</div>`}
function randomMenu(){return `${back()}<div class="pagehead"><h1>✨ ランダム出題</h1><p class="subtle">さまざまな作品から運命の出会いを。</p></div><div class="levels">${[['∞','無限モード','好きなだけ遊べる','infinite'],['50','50問チャレンジ','集中して実力を試す','50'],['100','100問チャレンジ','じっくり大冒険','100']].map(([e,t,d,n])=>`<button class="tile" data-random="${n}"><span class="icon">${e}</span><h3>${t}</h3><p>${d}</p></button>`).join('')}</div>`}
function works(){const groups=new Map();for(const c of getPlayable())for(const film of c.films){if(!groups.has(film))groups.set(film,[]);groups.get(film).push(c)}let items=[...groups].filter(([f])=>f.toLowerCase().includes(state.workSearch.toLowerCase())).sort((a,b)=>b[1].length-a[1].length);const chunk=items.slice(state.workPage*36,(state.workPage+1)*36);return `${back()}<div class="pagehead"><h1>🎬 作品別チャレンジ</h1><p class="subtle">好きな作品・シリーズを選ぼう。登録されているキャラクターだけ出題します。</p></div><div class="toolbar"><input class="field" id="workSearch" placeholder="作品名で検索（英語タイトル）" value="${escapeHTML(state.workSearch)}" aria-label="作品名で検索"></div><div class="works">${chunk.map(([f,c])=>`<button class="tile" data-work="${escapeHTML(f)}"><span class="icon">✧</span><h3>${escapeHTML(f)}</h3><p>${c.length} キャラクター</p></button>`).join('')}</div>${!chunk.length?'<div class="empty">該当する作品がありません。</div>':''}<div class="actions">${state.workPage>0?button('← 前へ','prevWorks','alt'):''}${items.length>(state.workPage+1)*36?button('次の作品 →','nextWorks','alt'):''}</div>`}
function textMenu(){return `${back()}<div class="pagehead"><h1>📝 文字ヒント検定</h1><p class="subtle">作品名とヒントを読んで名前を入力しよう。画像が未登録のキャラクターも出題！ 現在 ${getTextPlayable().length} キャラ。</p></div><div class="levels">${[['20','20問チャレンジ','まずは気軽に','20'],['50','50問チャレンジ','じっくり挑戦','50'],['100','100問チャレンジ','マニアへの道','100'],['∞','無限モード','何度でも遊ぼう','infinite']].map(([e,t,d,n])=>`<button class="tile" data-text="${n}"><span class="icon">${e}</span><h3>${t}</h3><p>${d}</p></button>`).join('')}</div><div class="panel"><h2>🎬 作品を指定して挑戦</h2><p class="subtle">『ズートピア2』『ピノキオ』など、追加した作品からも選べます。</p><div class="actions">${button('作品別・文字ヒント検定へ','textWorks','alt')}</div></div>`}
function textWorks(){
 const groups=new Map();
 for(const c of getTextPlayable())for(const film of c.films){if(!groups.has(film))groups.set(film,[]);groups.get(film).push(c);}
 const items=[...groups].filter(([f])=>f.toLowerCase().includes(state.workSearch.toLowerCase())).sort((a,b)=>b[1].length-a[1].length);
 const chunk=items.slice(state.workPage*36,(state.workPage+1)*36);
 return `${back()}<div class="pagehead"><h1>🎬 作品別・文字ヒント検定</h1><p class="subtle">作品を選んで最大20問。新しい作品にも挑戦できます。</p></div><div class="toolbar"><input class="field" id="workSearch" placeholder="英語の作品名で検索" value="${escapeHTML(state.workSearch)}" aria-label="作品名で検索"></div><div class="works">${chunk.map(([f,c])=>`<button class="tile" data-text-work="${escapeHTML(f)}"><span class="icon">📝</span><h3>${escapeHTML(f)}</h3><p>${c.length} キャラクター</p></button>`).join('')}</div>${!chunk.length?'<div class="empty">該当する作品がありません。</div>':''}<div class="actions">${state.workPage>0?button('← 前へ','prevWorks','alt'):''}${items.length>(state.workPage+1)*36?button('次の作品 →','nextWorks','alt'):''}</div>`;
}
function start(mode,list,target,label,style='image'){
 const pool=random(list.filter(x=>style==='text'?!!x.hint:(x.imageUrl&&x.imageOk!==false)));
 if(!pool.length){alert(style==='text'?'文字ヒント付きのキャラクターがありません。':state.loading?'画像データの読み込み中です。少ししてからお試しください。':'このコースには確認済み画像がまだありません。');return;}
 const size=target===Infinity?pool.length:Math.min(target,pool.length);
 state.mode={mode,target,label,pool,used:new Set(),infinite:target===Infinity,style};
 state.deck=pool.slice(0,size);state.pos=0;state.records=[];state.answer='';state.feedback=null;state.view='quiz';render();window.scrollTo({top:0,behavior:'instant'});
}
function current(){return state.deck[state.pos]}
function quiz(){
 const c=current();if(!c){finish();return result();}
 const isText=state.mode?.style==='text';
 const finite=!state.mode?.infinite;const total=finite?state.deck.length:'∞';
 const good=state.records.filter(x=>x.ok).length;
 const prompt=isText
  ? `<div class="hint-scene" role="group" aria-label="キャラクターのヒント"><div class="hint-symbol">📜 ✨</div><div class="hint-heading">キャラクターヒント</div><p class="hint-text">${escapeHTML(c.hint)}</p><div class="hint-work">🎬 ${escapeHTML(c.films[0])}</div></div>`
  : `<div class="portrait" id="portrait"><img id="characterImage" src="${escapeHTML(c.imageUrl)}" alt="キャラクター画像" referrerpolicy="no-referrer"></div>`;
 const feedback=state.feedback
  ? `<div class="feedback ${state.feedback.ok?'good':'bad'}"><h3>${state.feedback.ok?'✨ 正解！ よく知ってるね！':'🌙 おしい！ 次はきっとわかるよ'}</h3><div><b>正解：${escapeHTML(c.jp||c.name)}</b>${c.jp?`<p class="small">${escapeHTML(c.name)}</p>`:''}</div><div class="info-tags">${c.films.slice(0,5).map(f=>`<span>${escapeHTML(f)}</span>`).join('')}</div><p>${c.jp?`${escapeHTML(c.jp)}は『${escapeHTML(c.films[0])}』などに登場するキャラクターです。`:`『${escapeHTML(c.films[0])}』などに登場します。日本語名は未登録です。`}</p>${c.sourceUrl?`<a class="small" href="${escapeHTML(c.sourceUrl)}" target="_blank" rel="noopener noreferrer">作品・キャラクター情報を見る ↗</a>`:''}</div><div class="actions">${button('次の問題へ ✨','next','gold')}</div>`
  : `<form id="answerForm"><input class="field answer" id="answer" name="answer" autocomplete="off" placeholder="名前を入力してね" aria-label="キャラクター名を入力" required><div class="actions">${button('答える ✦','submit','gold')}</div></form>`;
 return `<div class="question"><div class="quiz-head"><span>✧ ${escapeHTML(state.mode.label)}</span><span>${state.pos+1} / ${total}　✓ ${good}</span></div>${finite?`<div class="progress"><i style="width:${(state.pos+1)/state.deck.length*100}%"></i></div>`:''}${prompt}<h2>このキャラクターの名前は？</h2>${!isText&&c.difficulty===1?`<p class="subtle small">作品のヒント：${escapeHTML(c.films[0])}</p>`:''}${feedback}${state.mode?.infinite?`<button class="topbtn" data-action="end">結果を見る（ここで終了）</button>`:''}</div>`;
}
function recordAnswer(){if(state.feedback)return;const value=document.getElementById('answer')?.value||'';if(!value.trim())return;const c=current();const ok=isCorrect(value,c);state.feedback={ok,value};state.records.push({id:c.id,ok,value,c});if(!ok){history.wrong[c.id]=true;save()}else if(history.wrong[c.id]){delete history.wrong[c.id];save()}render()}
function next(){
 state.feedback=null;state.answer='';state.pos++;
 if(state.pos>=state.deck.length){
  if(state.mode.infinite){
   const pool=random(state.mode.pool.filter(c=>state.mode.style==='text'?!!c.hint:c.imageOk!==false));
   if(!pool.length){finish();return;}
   state.deck=pool;state.pos=0;
  }else{finish();return;}
 }
 render();window.scrollTo({top:0,behavior:'instant'});
}
function finish(){const good=state.records.filter(x=>x.ok).length;history.bests.unshift({label:state.mode.label,score:good,total:state.records.length,date:new Date().toISOString()});history.bests=history.bests.slice(0,25);save();state.view='result';render()}
function result(){
 const total=state.records.length;const correct=state.records.filter(r=>r.ok).length;
 const pct=total?Math.round(correct/total*100):0;const rank=pct>=95?'SS':pct>=85?'S':pct>=70?'A':pct>=50?'B':'C';
 const wrong=state.records.filter(r=>!r.ok);
 return `${back()}<div class="hero"><div class="eyebrow">YOUR MAGICAL RESULT</div><div class="moon">✦</div><h1>チャレンジ結果</h1><p>おつかれさま！ 今日の魔法の実力は…</p><div class="rank">${rank} RANK</div></div><div class="statrow"><div class="stat"><strong>${correct}</strong><small>正解数</small></div><div class="stat"><strong>${total}</strong><small>問題数</small></div><div class="stat"><strong>${pct}%</strong><small>正答率</small></div></div><div class="panel"><h2>✧ 間違えたキャラクター (${wrong.length})</h2>${wrong.length?wrong.map(r=>`<div class="wrongrow">${state.mode?.style==='text'?'<div class="clue-thumb">📜</div>':`<img src="${escapeHTML(r.c.imageUrl)}" alt="キャラクター画像" referrerpolicy="no-referrer">`}<div><b>${escapeHTML(r.c.jp||r.c.name)}</b><p>あなたの答え：${escapeHTML(r.value)}</p><p>${escapeHTML(r.c.films[0]||'')}</p></div></div>`).join(''):'<p class="subtle">全部正解！ すばらしい！</p>'}</div><div class="actions">${button('もう一度','again')}${button('間違いを復習','review','alt')}${button('ホームへ','home','alt')}</div>`;
}
function review(){
 const images=getPlayable().filter(c=>history.wrong[c.id]);
 const texts=getTextPlayable().filter(c=>history.wrong[c.id]);
 if(!images.length&&!texts.length)return `${back()}<div class="panel empty"><div class="moon">✧</div><h2>復習する問題はまだないよ</h2><p>クイズで間違えたキャラクターがここにたまります。</p>${button('クイズを選ぶ','home')}</div>`;
 return `${back()}<div class="panel"><h1>💫 復習の魔法</h1><p class="subtle">間違えたキャラクターに再チャレンジ！ 正解すると復習リストから卒業します。</p><div class="actions">${images.length?button(`画像クイズを復習 (${images.length}件)`,'startReview','gold'):''}${texts.length?button(`文字ヒントを復習 (${texts.length}件)`,'startTextReview','gold'):''}</div></div>`;
}
function render(){
 app.innerHTML=header()+({home,levels,works,random:randomMenu,text:textMenu,textWorks,quiz,result,review}[state.view]||home)();
 if(state.view==='quiz'&&!state.feedback){
  document.getElementById('answer')?.focus({preventScroll:true});
  if(state.mode?.style!=='image')return;
  const image=document.getElementById('characterImage');
  if(image)image.onerror=()=>{
   const c=current();if(!c)return;
   c.imageOk=false;state.ready=getPlayable().length;state.deck.splice(state.pos,1);
   if(state.mode?.infinite&&!state.deck.length){state.deck=random(getPlayable());state.pos=0;}
   if(state.pos>=state.deck.length){
    if(state.records.length)finish();else{state.view='home';render();}
   }else render();
  };
 }
}
app.addEventListener('submit',e=>{if(e.target.id==='answerForm'){e.preventDefault();recordAnswer()}});
app.addEventListener('input',e=>{if(e.target.id==='workSearch'){const selection=e.target.selectionStart;state.workSearch=e.target.value;state.workPage=0;render();const field=document.getElementById('workSearch');field?.focus();field?.setSelectionRange(selection,selection)}});
app.addEventListener('click',e=>{
 const textWork=e.target.closest('[data-text-work]');
 if(textWork){const film=textWork.dataset.textWork;start('textWork',getTextPlayable().filter(c=>c.films.includes(film)),20,`文字ヒント・${film}`,'text');return;}
 const work=e.target.closest('[data-work]');
 if(work){const film=work.dataset.work;start('work',getPlayable().filter(c=>c.films.includes(film)),20,film);return;}
 const level=e.target.closest('[data-level]');
 if(level){const n=Number(level.dataset.level);start('level',getPlayable().filter(c=>c.difficulty===n),20,['','初級','中級','上級','超上級'][n]);return;}
 const randomBtn=e.target.closest('[data-random]');
 if(randomBtn){const n=randomBtn.dataset.random;start('random',getPlayable(),n==='infinite'?Infinity:Number(n),n==='infinite'?'無限モード':`${n}問チャレンジ`);return;}
 const textBtn=e.target.closest('[data-text]');
 if(textBtn){const n=textBtn.dataset.text;start('text',getTextPlayable(),n==='infinite'?Infinity:Number(n),n==='infinite'?'文字ヒント・無限モード':`文字ヒント・${n}問`,'text');return;}
 const btn=e.target.closest('[data-action]');if(!btn)return;
 const a=btn.dataset.action;
 if(['home','levels','works','random','text','textWorks','review'].includes(a)){state.view=a;render();return;}
 if(a==='submit'){recordAnswer();return;}
 if(a==='next'){next();return;}
 if(a==='end'){finish();return;}
 if(a==='startReview'){const q=getPlayable().filter(c=>history.wrong[c.id]);start('review',q,q.length,'画像復習モード');return;}
 if(a==='startTextReview'){const q=getTextPlayable().filter(c=>history.wrong[c.id]);start('review',q,q.length,'文字ヒント復習モード','text');return;}
 if(a==='again'){start(state.mode.mode,state.mode.mode==='review'?(state.mode.style==='text'?getTextPlayable():getPlayable()).filter(c=>history.wrong[c.id]):state.mode.pool,state.mode.target,state.mode.label,state.mode.style);return;}
 if(a==='nextWorks'||a==='prevWorks'){state.workPage+=a==='nextWorks'?1:-1;render();return;}
});
// Only explicitly reviewed local images can enter the quiz. No API or legacy cache fallback.
async function init(){
 try{
  const r=await fetch('./images/manifest.json',{cache:'no-store'});
  if(!r.ok)throw Error('manifest');
  const manifest=await r.json();createCatalog(manifest);
  if(!getPlayable().length)state.error='画像付き問題はまだありません。文字ヒント検定は利用できます。';
 }catch{
  createCatalog();
  state.error='画像一覧を読み込めませんでした。既存の images/manifest.json を維持してください。文字ヒント検定は利用できます。';
 }
 state.loading=false;render();
}
init();
