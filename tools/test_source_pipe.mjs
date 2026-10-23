// Exercise the real scanner through a delayed, fragmented subprocess pipe.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';

const scanner = new URL('../skills/business-observer/scripts/bo_observer/adapters/javascript/scan.mjs', import.meta.url);

async function parse(input) {
  const child = spawn(process.execPath, ['--input-type=module', '-e',
    `process.stderr.write('ready\\n'); await import(${JSON.stringify(scanner.href)});`],
    {stdio: ['pipe', 'pipe', 'pipe']});
  const stdout = [], stderr = [];
  let started;
  const ready = new Promise(resolve => { started = resolve; });
  child.stdout.on('data', chunk => stdout.push(chunk));
  child.stderr.on('data', chunk => { stderr.push(chunk); started(); });
  const closed = new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', (code, signal) => resolve({code, signal}));
  });
  // The child must not crash while waiting for the first or next input chunk.
  let writeError;
  child.stdin.on('error', error => { writeError = error; });
  const timeout = setTimeout(() => child.kill(), 15000);
  try {
    await Promise.race([ready, closed]);
    await delay(300);
    // One-byte writes deliberately split the initial multibyte path character.
    const boundaries = [...Array(Math.min(input.length, 64)).keys()].map(i => i + 1);
    for (let offset = 64; offset < input.length; offset += 4096) boundaries.push(Math.min(offset + 4096, input.length));
    let offset = 0;
    for (const end of boundaries) {
      if (writeError || child.exitCode !== null) break;
      await new Promise(resolve => child.stdin.write(input.subarray(offset, end), error => {
        if (error) writeError = error;
        resolve();
      }));
      offset = end;
      await delay(1);
    }
    child.stdin.end();
    return {...await closed, stdout: Buffer.concat(stdout).toString('utf8'),
      stderr: Buffer.concat(stderr).toString('utf8'), writeError: writeError?.message};
  } finally {
    clearTimeout(timeout);
    if (child.exitCode === null) child.kill();
  }
}

const request = {files: [
  {path: '审查.ts', source: `export function 审查(value: string) { return value.length; }\nexport const text = ${JSON.stringify('绘画'.repeat(24000))};`},
  {path: 'panel.tsx', source: 'export function Panel() { const click = () => 1; return <button onClick={click}/>; }'},
]};
const bytes = Buffer.from(JSON.stringify(request));
assert(bytes.length > 131072, 'The request must exceed common pipe buffer sizes.');
const valid = await parse(bytes);
assert.equal(valid.code, 0, valid.stderr + '\n' + valid.writeError);
const result = JSON.parse(valid.stdout);
assert.deepEqual(result.errors, []);
assert.equal(result.units['审查.ts'].symbols['审查'].id, '审查.ts::审查');
assert(result.units['panel.tsx'].symbols['Panel.click']);
for (const invalid of [Buffer.alloc(0), bytes.subarray(0, bytes.length - 1)]) {
  const failure = await parse(invalid);
  assert.notEqual(failure.code, 0, 'Incomplete JSON must fail instead of producing an empty graph.');
  assert.match(failure.stderr, /SyntaxError/);
}
const syntax = await parse(Buffer.from(JSON.stringify({files: [{path: 'broken.ts', source: 'export function ('}]})));
assert.equal(syntax.code, 0, syntax.stderr);
assert.equal(JSON.parse(syntax.stdout).errors[0].path, 'broken.ts');
console.log('PASS: large fragmented UTF-8 source input; empty/truncated JSON and invalid source remain explicit failures.');
