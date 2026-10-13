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
const skill = join(workspace, 'SKILL.md');
writeFileSync(skill, 'Application-owned participant schema instructions.');
const specification = {root:bundle, candidate, reads:[worklist,skill], source_ranges:[[1,1],[3,3]],
                       python:'/usr/bin/synthetic-python', helper:join(workspace,'owned-helper.py'), stage:'participants'};
function spec(value) {writeFileSync(specPath, JSON.stringify(value), {mode:0o600}); chmodSync(specPath,0o600);}
spec(specification);
process.env.RECORDPREP_NATIVE_ACCESS_SPEC = specPath;
let calls = [];
function harness(response = {code:0, stdout:'Candidate valid.\nRECORDPREP_PARTICIPANT_PROGRESS={"reviewed":1,"total":2,"complete":false}'}) {
  const handlers = {}, tools = {};
  factory({on:(name,fn)=>handlers[name]=fn, registerTool:tool=>tools[tool.name]=tool,
           exec:async (command,args,options)=>{ calls.push({command,args,options}); return response; }});
  return {handlers,tools};
}
const h = harness();
let shutdowns = 0;
const ctx = {cwd:workspace, shutdown:()=>{ shutdowns++; }};
async function guard(toolName,path) {return h.handlers.tool_call({toolName,input:{path}},ctx);}
for (const path of [source,candidate,worklist,skill]) assert.equal(await guard('read',path),undefined);
for (const tool of ['write','edit']) {
  assert.equal(await guard(tool,candidate),undefined);
  for (const path of [source,published,specPath,skill,join(workspace,'extra.json')]) assert.equal((await guard(tool,path)).block,true);
}
for (const path of [outsideScope,escaped,join(root,'private.txt'),published,`${workspace}/../workspace/candidate.json`]) {
  assert.equal((await guard('read',path)).block,true);
}
for (const tool of ['bash','exec','codemode','arbitrary_profile_tool']) assert.equal((await guard(tool,candidate)).block,true);
assert.equal(h.tools.recordprep_validate_candidate.executionMode,'sequential');
assert.equal((await h.tools.recordprep_validate_candidate.execute('id',{partial:true},undefined)).details.valid,true);
assert.deepEqual(calls[0].args,[specification.helper,'validate',bundle,'--normalize','--partial']);
assert.equal(calls[0].command,specification.python);
assert.equal(calls[0].options.timeout,120000);
// Linked candidates cannot redirect edits/publication or validation to a final.
unlinkSync(candidate);
linkSync(published,candidate);
assert.equal((await guard('write',candidate)).block,true);
assert.equal((await guard('read',candidate)).block,true);
assert.equal((await h.tools.recordprep_validate_candidate.execute('id',{partial:false},undefined,undefined,ctx)).isError,true);
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
// Actual stderr diagnostics reach the model and failure loops are bounded.
const failing = harness({code:1,stdout:'',stderr:'participant-index validation: hearing 1 has an invalid page range.'});
let reply = await failing.tools.recordprep_validate_candidate.execute('bad1',{partial:true},undefined,undefined,ctx);
assert.match(reply.content[0].text,/invalid page range/);
assert.match(reply.content[0].text,/One repair attempt/);
assert.equal(reply.terminate,undefined);
reply = await failing.tools.recordprep_validate_candidate.execute('bad2',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,true);
assert.match(reply.content[0].text,/two failed attempts/);
assert.equal(shutdowns,1);
assert.equal((await failing.handlers.tool_call({toolName:'write',input:{path:candidate}},ctx)).block,true);
unlinkSync(join(workspace,'participant-validation-failed'));
// A successful full validation ends the stage without a perfection/refinement loop.
const success = harness();
reply = await success.tools.recordprep_validate_candidate.execute('done',{partial:false},undefined,undefined,ctx);
assert.equal(reply.terminate,true);
assert.equal(reply.details.valid,true);
assert.equal((await success.handlers.tool_call({toolName:'edit',input:{path:candidate}},ctx)).block,true);
// A partial request finishes when Python independently finds the whole index valid.
const partialComplete = harness({code:0,stdout:'Quality warnings retained.\nRECORDPREP_PARTICIPANT_PROGRESS={"reviewed":1,"total":1,"complete":true}'});
reply = await partialComplete.tools.recordprep_validate_candidate.execute('complete',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,true);
assert.equal(reply.details.complete,true);
assert.equal(reply.isError,false);
// Repeated successful partial checks without reviewing more hearings cannot loop.
const stalled = harness();
reply = await stalled.tools.recordprep_validate_candidate.execute('partial1',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,undefined);
reply = await stalled.tools.recordprep_validate_candidate.execute('partial2',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,true);
assert.equal(reply.details.noProgress,true);
assert.equal(reply.isError,true);
assert.equal((await stalled.handlers.tool_call({toolName:'write',input:{path:candidate}},ctx)).block,true);
unlinkSync(join(workspace,'participant-validation-failed'));
// Genuine progress across batches remains allowed; only the complete batch ends work.
const advancingReply = {code:0,stdout:'RECORDPREP_PARTICIPANT_PROGRESS={"reviewed":1,"total":3,"complete":false}'};
const advancing = harness(advancingReply);
reply = await advancing.tools.recordprep_validate_candidate.execute('batch1',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,undefined);
advancingReply.stdout = 'RECORDPREP_PARTICIPANT_PROGRESS={"reviewed":2,"total":3,"complete":false}';
reply = await advancing.tools.recordprep_validate_candidate.execute('batch2',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,undefined);
advancingReply.stdout = 'RECORDPREP_PARTICIPANT_PROGRESS={"reviewed":3,"total":3,"complete":true}';
reply = await advancing.tools.recordprep_validate_candidate.execute('batch3',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,true);
assert.equal(reply.isError,false);
// A missing helper progress record cannot silently authorize endless partial checks.
const missingProgress = harness({code:0,stdout:'No progress record'});
reply = await missingProgress.tools.recordprep_validate_candidate.execute('missing1',{partial:true},undefined,undefined,ctx);
assert.equal(reply.isError,true);
reply = await missingProgress.tools.recordprep_validate_candidate.execute('missing2',{partial:true},undefined,undefined,ctx);
assert.equal(reply.terminate,true);
unlinkSync(join(workspace,'participant-validation-failed'));
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
