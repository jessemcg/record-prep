// Offline execution of the actual read/write guard and successful-read accounting.
import assert from 'node:assert/strict';
import {mkdirSync, writeFileSync, readFileSync, symlinkSync, unlinkSync, chmodSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath),'../lib/node_modules/@earendil-works/pi-coding-agent');
const require = createRequire(join(pkg,'package.json'));
const {createJiti} = require('jiti');
const jiti = createJiti(import.meta.url,{moduleCache:false});
const factory = await jiti.import(resolve('.pi/extensions/recordprep-classification-review-tools.ts'),{default:true});
const {createReadTool} = await import(pathToFileURL(join(pkg,'dist/index.js')));
globalThis.fetch = () => {throw new Error('Network forbidden');};
const root = process.env.RECORDPREP_GUARD_TEST_ROOT;
mkdirSync(root,{recursive:true,mode:0o700}); chmodSync(root,0o700);
const candidate = join(root,'candidate.json'), source = join(root,'block-0001.jsonl'), other = join(root,'private-config.json');
const spec = join(root,'access.json'), journal = join(root,'reads.jsonl');
writeFileSync(source,'{"file_name":"0001.txt","page_type":"CT_other"}\n');
writeFileSync(other,'Private synthetic canary');
writeFileSync(spec,JSON.stringify({reads:[source],candidate,journal}),{mode:0o600});
process.env.RECORDPREP_CLASSIFICATION_REVIEW_ACCESS_SPEC = spec;
const handlers = {};
factory({on:(name,fn)=>handlers[name]=fn});
const guard = (toolName,path)=>handlers.tool_call({toolName,input:{path}},{cwd:root});
assert.equal(await guard('read',source),undefined);
const result = await createReadTool(root).execute('read1',{path:source},undefined,undefined);
await handlers.tool_result({toolName:'read',input:{path:source},...result,isError:false},{cwd:root});
assert.equal(JSON.parse(readFileSync(journal,'utf8').trim()),source);
assert.equal(await guard('write',candidate),undefined);
writeFileSync(candidate,'{}');
assert.equal(await guard('edit',candidate),undefined);
for (const tool of ['bash','grep','ls','find','codemode','unknown']) assert.equal((await guard(tool,source)).block,true);
for (const path of [source,other,spec,journal,join(root,'published.jsonl')]) {
  assert.equal((await guard('write',path)).block,true);
  assert.equal((await guard('edit',path)).block,true);
}
for (const path of [other,spec,journal,root+'/../'+root.split('/').at(-1)+'/block-0001.jsonl']) assert.equal((await guard('read',path)).block,true);
const before=readFileSync(journal,'utf8');
await handlers.tool_result({toolName:'read',input:{path:source},isError:true},{cwd:root});
assert.equal(readFileSync(journal,'utf8'),before);
unlinkSync(candidate); symlinkSync(other,candidate);
assert.equal((await guard('write',candidate)).block,true);
assert.equal((await guard('read',candidate)).block,true);
assert.equal((await handlers.user_bash()).result.exitCode,1);
// A pre-existing journal must fail closed, not bless forged read evidence.
const blocked={}; factory({on:(n,f)=>blocked[n]=f});
assert.equal((await blocked.tool_call({toolName:'read',input:{path:source}},{cwd:root})).block,true);
console.log('Classification review guard and real SDK read: PASS');
