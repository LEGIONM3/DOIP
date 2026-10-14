const fs = require('fs');
const path = require('path');
function walk(dir) {
  let res = [];
  fs.readdirSync(dir).forEach(f => {
    const full = path.join(dir, f);
    if (fs.statSync(full).isDirectory()) res = res.concat(walk(full));
    else if (f.endsWith('.tsx')) res.push(full);
  });
  return res;
}

const files = walk('src');
const nonButtonClicks = [];
files.forEach(file => {
  const code = fs.readFileSync(file, 'utf8');
  const regex = /<(div|span|li|tr|p)\b([^>]*?onClick\s*=[^>]*?)>/g;
  let m;
  while ((m = regex.exec(code)) !== null) {
    const line = code.substring(0, m.index).split('\n').length;
    nonButtonClicks.push({ file, line, tag: m[1], snippet: m[0].replace(/\s+/g, ' ').slice(0, 90) });
  }
});
console.log('Non-button elements with onClick:', nonButtonClicks.length);
nonButtonClicks.forEach(c => console.log(c.file + ':' + c.line + ' <' + c.tag + '> -> ' + c.snippet));
