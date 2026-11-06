const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const curated=JSON.parse(fs.readFileSync(path.join(root,'data.js'),'utf8').split('=')[1].trim().replace(/;$/,''));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'images/manifest.json'),'utf8'));
const app={innerHTML:'',addEventListener(){}};
let answer='';
const context=vm.createContext({curated,console,window:{scrollTo(){}},localStorage:{getItem(){return null},setItem(){}},document:{getElementById(id){return id==='app'?app:id==='answer'?{value:answer,focus(){}}:null}},alert(message){throw Error(message)}});
const source=fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/^import[^\n]+\n/,'').replace(/init\(\);\s*$/,'');
vm.runInContext(source,context);
context.manifest=manifest;
vm.runInContext('createCatalog(manifest)',context);
const run=s=>vm.runInContext(s,context);
assert.equal(run('getPlayable().length'),200);
assert.equal(run('getPlayable().filter(c=>c.difficulty===1).length'),37);
for(const [id,m] of Object.entries(manifest)){
 assert.ok(curated.some(c=>c.id===id));assert.equal(id,m.characterId);assert.equal(m.singleCharacter,true);
 assert.ok(fs.existsSync(path.join(root,m.path)));
}
// Legacy strings, wrong identities and group images must never enter a deck.
run('createCatalog({"mickey-&-friends-0":"images/mickey.webp"})');assert.equal(run('getPlayable().length'),0);
for(const patch of [{characterId:'wrong'},{singleCharacter:false},{reviewed:false},{path:'images/../bad.webp'}]){
 context.bad={...manifest['mickey-&-friends-0'],...patch};
 run('createCatalog({"mickey-&-friends-0":bad})');assert.equal(run('getPlayable().length'),0);
}
run('createCatalog(manifest)');
assert.ok(run('isCorrect("みっきー",curated[0])'));
assert.ok(run('isCorrect("Mickey Mouse",curated[0])'));
assert.equal(run('isCorrect("ミニー",curated[0])'),false);
assert.equal(run('isCorrect("Mickey Mause",curated[0])'),false);
assert.equal(run('isCorrect("",curated[0])'),false);
run('start("level",getPlayable().filter(c=>c.difficulty===1),20,"初級")');
assert.equal(run('state.deck.length'),20);assert.equal(run('new Set(state.deck.map(c=>c.id)).size'),20);
assert.ok(run('state.deck.every(c=>c.difficulty===1&&c.imageReviewed)'));
// Complete a full round through the actual grading and next-question functions.
for(let i=0;i<20;i++){answer=run('current().jp');run('recordAnswer()');assert.ok(run('state.feedback.ok'));run('next()');}
assert.equal(run('state.view'),'result');assert.equal(run('state.records.length'),20);
// Review, completion and repeat must stay finite.
run('history.wrong[state.catalog[0].id]=true;start("review",getPlayable().filter(c=>history.wrong[c.id]),1,"復習モード")');
answer='不正解';run('recordAnswer();next()');assert.equal(run('state.view'),'result');
run('start(state.mode.mode,getPlayable().filter(c=>history.wrong[c.id]),state.mode.target,state.mode.label)');
assert.equal(run('state.mode.infinite'),false);
// Broken images are removed without charging an incorrect answer.
run('state.deck[0].imageOk=false');assert.equal(run('getPlayable().some(c=>c.id===state.deck[0].id)'),false);
console.log('PASS: manifest integrity, approval gates, beginner pool, aliases, 20-question round, finite review and broken-image filtering');
const additions=JSON.parse(fs.readFileSync(path.join(root,'images/additions-200.json'),'utf8'));
assert.equal(additions.length,60);
assert.equal(new Set(additions.map(c=>c.id)).size,60);
for(const entry of additions){
 const character=curated.find(c=>c.id===entry.id);context.newCharacter=character;
 for(const value of [character.jp,character.name,...character.aliases]){context.guess=value;assert.ok(run('isCorrect(guess,newCharacter)'),entry.id+': '+value);}
 assert.ok(character.sourceUrl.startsWith('https://'));
 assert.equal(manifest[entry.id].path,entry.path);
}
assert.equal(manifest['luca-2'],undefined);assert.equal(manifest['lightyear-0'],undefined);
assert.deepEqual(curated.find(c=>c.id==='inside-out-5').films,['Inside Out 2']);
assert.deepEqual(curated.find(c=>c.id==='toy-story-8').films,['Toy Story 4']);
console.log('PASS: all 60 additions and their answer aliases, source links, group-image rejection and sequel titles');
