const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname,'..');
const curated = JSON.parse(fs.readFileSync(path.join(root,'data.js'),'utf8').replace(/^export const curated\s*=\s*/, '').replace(/;\s*$/, ''));
const appCode = fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/^import[^\n]*\n/, '');
const callbacks={};
const app={innerHTML:'',addEventListener:(name,handler)=>callbacks[name]=handler};
let answerInput={value:'',focus:()=>{}};
const imageElement={onerror:null};
const document={getElementById(id){if(id==='app')return app;if(id==='answer')return answerInput;if(id==='characterImage')return imageElement;return null;}};
const localStorage={_data:new Map(),getItem(k){return this._data.get(k)||null;},setItem(k,v){this._data.set(k,v);}};
const manifest={'mickey-&-friends-0':{reviewed:true,singleCharacter:true,characterId:'mickey-&-friends-0',path:'images/mickey.webp'}};
const context=vm.createContext({curated,document,window:{scrollTo:()=>{}},localStorage,fetch:async()=>({ok:true,json:async()=>manifest}),alert:(msg)=>{throw Error('Unexpected alert: '+msg);},console});
vm.runInContext(appCode,context,{filename:'app.js'});
function click(selector,attribute,value){
 assert(callbacks.click);
 const target={closest:(query)=>query===selector?{dataset:{[attribute]:value}}:null};
 callbacks.click({target});
}
const hit=(x)=>assert(app.innerHTML.includes(x),`Expected ${x} in ${app.innerHTML.slice(0,350)}`);
(async()=>{
 await new Promise(r=>setImmediate(r));
 hit('621 キャラ');hit('文字ヒント検定');hit('画像付き 1 キャラ');
 click('[data-action]','action','text');hit('20問チャレンジ');
 click('[data-text]','text','20');hit('キャラクターヒント');
 for(let i=0;i<20;i++){
  answerInput.value='xyz-not-an-answer';click('[data-action]','action','submit');hit('正解：');
  click('[data-action]','action','next');
 }
 hit('チャレンジ結果');hit('間違えたキャラクター (20)');
 click('[data-action]','action','review');hit('文字ヒントを復習 (20件)');
 click('[data-action]','action','startTextReview');hit('キャラクターヒント');
 click('[data-action]','action','home');
 click('[data-action]','action','text');
 click('[data-action]','action','textWorks');hit('作品別・文字ヒント検定');
 click('[data-text-work]','textWork','Zootopia 2');hit('キャラクターヒント');
 click('[data-action]','action','home');
 click('[data-action]','action','levels');hit('初級');
 click('[data-level]','level','1');hit('images/mickey.webp');
 answerInput.value='ミッキーマウス';click('[data-action]','action','submit');hit('正解！');
 click('[data-action]','action','next');hit('チャレンジ結果');
 console.log('PASS: UI smoke (home, 20 text questions, wrong-answer review, text work selection, image quiz, scoring)');
})().catch(err=>{console.error(err);process.exitCode=1;});
