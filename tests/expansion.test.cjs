const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const text = fs.readFileSync(path.join(root,'data.js'),'utf8');
const data = JSON.parse(text.replace(/^export const curated\s*=\s*/, '').replace(/;\s*$/, ''));
const additions = JSON.parse(fs.readFileSync(path.join(root,'new_characters.json'),'utf8'));
const summary = JSON.parse(fs.readFileSync(path.join(root,'expansion-summary.json'),'utf8'));
assert.equal(data.length, summary.total_count);
assert.equal(additions.length, summary.added_count);
assert.equal(data.length-additions.length, summary.original_count);
assert.equal(new Set(data.map(c=>c.id)).size, data.length, 'Duplicate id');
for (const c of data) {
 assert(c.id && c.name && c.jp && c.films?.length && [1,2,3,4].includes(c.difficulty), `Invalid: ${c.id}`);
 assert(['Disney','Pixar'].includes(c.franchise), `Invalid franchise: ${c.id}`);
}
for (const c of additions) {
 assert(c.hint?.length >= 6, `Missing clue: ${c.id}`);
 assert(data.some(x=>x.id===c.id), `Missing added character: ${c.id}`);
 assert(c.id.startsWith('extended-'), `Wrong new id prefix: ${c.id}`);
}
const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert(app.includes('getTextPlayable') && app.includes('startTextReview'));
assert(app.includes('manifest[c.id]') && app.includes('m?.reviewed===true'));
assert(html.includes('quiz-extra.css') && html.includes('styles.css'));
console.log(`PASS: ${summary.original_count} preserved + ${summary.added_count} added = ${summary.total_count} characters, ${summary.total_works} works`);
