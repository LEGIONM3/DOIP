const fs = require('fs');
const path = require('path');

function walk(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    const full = path.join(dir, file);
    const stat = fs.statSync(full);
    if (stat && stat.isDirectory()) {
      results = results.concat(walk(full));
    } else if (file.endsWith('.tsx')) {
      results.push(full);
    }
  });
  return results;
}

const files = walk('src');
console.log('Total TSX files:', files.length);

const issues = [];

files.forEach(f => {
  const content = fs.readFileSync(f, 'utf8');
  
  // Check for button without onClick or type=submit
  const buttonRegex = /<button\b([^>]*?)>/g;
  let match;
  while ((match = buttonRegex.exec(content)) !== null) {
    const attrs = match[1];
    const hasOnClick = /onClick\s*=/.test(attrs);
    const isSubmit = /type\s*=\s*['"]submit['"]/.test(attrs);
    const isFormTrigger = /form\s*=/.test(attrs);
    
    if (!hasOnClick && !isSubmit && !isFormTrigger) {
      const lineNum = content.substring(0, match.index).split('\n').length;
      issues.push({ file: f, line: lineNum, type: 'BUTTON_NO_ACTION', snippet: match[0].replace(/\s+/g, ' ').slice(0, 100) });
    }
  }

  // Check for Link or a without to/href or with #
  const linkRegex = /<(Link|a)\b([^>]*?)>/g;
  while ((match = linkRegex.exec(content)) !== null) {
    const attrs = match[2];
    const hasTo = /to\s*=/.test(attrs);
    const hasHref = /href\s*=/.test(attrs);
    const hasEmpty = /to\s*=\s*['"](#|\s*)['"]|href\s*=\s*['"](#|\s*)['"]/.test(attrs);
    if ((!hasTo && !hasHref) || hasEmpty) {
      const lineNum = content.substring(0, match.index).split('\n').length;
      issues.push({ file: f, line: lineNum, type: 'EMPTY_OR_MISSING_LINK', snippet: match[0].replace(/\s+/g, ' ').slice(0, 100) });
    }
  }
});

console.log('Total issues found:', issues.length);
issues.forEach(i => console.log(`[${i.type}] ${i.file}:${i.line} -> ${i.snippet}`));
