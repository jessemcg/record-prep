// Offline execution of the actual application-owned native guard extension.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, symlinkSync, chmodSync, linkSync, unlinkSync, renameSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
const require = createRequire(join(pkg, 'package.json'));
const { createJiti } = require('jiti');
const jiti = createJiti(import.meta.url, { moduleCache: false, alias: { typebox: require.resolve('typebox') } });
const factory = await jiti.import(resolve('.pi/extensions/recordprep-profile-native-tools.ts'), { default: true });
globalThis.fetch = () => { throw new Error('Network forbidden'); };
const root = process.env.RECORDPREP_GUARD_TEST_ROOT;
const bundle = join(root, 'bundle');
const workspace = join(root, 'workspace');
mkdirSync(join(bundle, 'text_pages'), {recursive:true});
mkdirSync(join(bundle, 'artifacts'), {recursive:true});
mkdirSync(workspace, {mode:0o700});
const candidate = join(workspace, 'candidate.json');
const source = join(bundle, 'text_pages/0001.txt');
const outsideScope = join(bundle, 'text_pages/0002.txt');
const published = join(bundle, 'artifacts/participant_index.json');
const worklist = join(workspace, 'worklist.json');
for (const path of [candidate, source, outsideScope, published, worklist]) writeFileSync(path, '{}');
const escaped = join(bundle, 'text_pages/0003.txt');
symlinkSync(join(root, 'private.txt'), escaped);
writeFileSync(join(root, 'private.txt'), 'PRIVATE_CANARY');
const specPath = join(workspace, 'access.json');
const specification = {root:bundle, candidate, reads:[worklist], source_ranges:[[1,1],[3,3]],
                       python:'/usr/bin/synthetic-python', helper:join(workspace,'owned-helper.py'), stage:'participants'};
function spec(value) {writeFileSync(specPath, JSON.stringify(value), {mode:0o600}); chmodSync(specPath,0o600);}
spec(specification);
process.env.RECORDPREP_NATIVE_ACCESS_SPEC = specPath;
let calls = [];
function harness() {
  const handlers = {}, tools = {};
  factory({on:(name,fn)=>handlers[name]=fn, registerTool:tool=>tools[tool.name]=tool,
           exec:async (command,args,options)=>{ calls.push({command,args,options}); return {code:0,stdout:'Candidate valid.'}; }});
  return {handlers,tools};
}
const h = harness();
const ctx = {cwd:workspace};
async function guard(toolName,path) {return h.handlers.tool_call({toolName,input:{path}},ctx);}
for (const path of [source,candidate,worklist]) assert.equal(await guard('read',path),undefined);
for (const tool of ['write','edit']) {
  assert.equal(await guard(tool,candidate),undefined);
  for (const path of [source,published,specPath,join(workspace,'extra.json')]) assert.equal((await guard(tool,path)).block,true);
}
for (const path of [outsideScope,escaped,join(root,'private.txt'),published,`${workspace}/../workspace/candidate.json`]) {
  assert.equal((await guard('read',path)).block,true);
}
for (const tool of ['bash','exec','codemode','arbitrary_profile_tool']) assert.equal((await guard(tool,candidate)).block,true);
assert.equal(h.tools.recordprep_validate_candidate.executionMode,'sequential');
assert.equal((await h.tools.recordprep_validate_candidate.execute('id',{partial:true},undefined)).details.valid,true);
assert.deepEqual(calls[0].args,[specification.helper,'validate',bundle,'--partial']);
assert.equal(calls[0].command,specification.python);
assert.equal(calls[0].options.timeout,120000);
// Linked candidates cannot redirect edits/publication or validation to a final.
unlinkSync(candidate);
linkSync(published,candidate);
assert.equal((await guard('write',candidate)).block,true);
assert.equal((await guard('read',candidate)).block,true);
await assert.rejects(h.tools.recordprep_validate_candidate.execute('id',{partial:false},undefined));
unlinkSync(candidate);
writeFileSync(candidate,'{}');
// A source inode shared with an unrelated private file is not authorized either.
linkSync(source,join(root,'source-alias.txt'));
assert.equal((await guard('read',source)).block,true);
unlinkSync(join(root,'source-alias.txt'));
// Replacing an approved parent directory with a link must not widen access.
renameSync(join(bundle,'text_pages'),join(bundle,'moved-pages'));
symlinkSync(join(bundle,'moved-pages'),join(bundle,'text_pages'));
assert.equal((await guard('read',source)).block,true);
unlinkSync(join(bundle,'text_pages'));
renameSync(join(bundle,'moved-pages'),join(bundle,'text_pages'));
assert.equal(await guard('read',source),undefined);
// Overview gets only explicit prepared inputs, not original pages/old participants.
spec({...specification,stage:'overview',source_ranges:[],helper:null});
const overview = harness();
assert.equal((await overview.handlers.tool_call({toolName:'read',input:{path:source}},ctx)).block,true);
assert.equal((await overview.handlers.tool_call({toolName:'recordprep_validate_candidate',input:{partial:false}},ctx)).block,true);
assert.equal(await overview.handlers.tool_call({toolName:'read',input:{path:worklist}},ctx),undefined);
assert.equal(await overview.handlers.tool_call({toolName:'write',input:{path:candidate}},ctx),undefined);
// Missing/malformed transport fails closed, including read and the validator.
spec({});
const broken = harness();
assert.equal((await broken.handlers.tool_call({toolName:'read',input:{path:source}},ctx)).block,true);
await assert.rejects(broken.tools.recordprep_validate_candidate.execute('id',{partial:false},undefined));
console.log('Native profile boundary contract passed');
