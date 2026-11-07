// Actual native organization guard; synthetic files only, no model/network.
import assert from 'node:assert/strict';
import {mkdirSync, writeFileSync, symlinkSync, linkSync, unlinkSync, chmodSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {createRequire} from 'node:module';
const pkg=process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath),'../lib/node_modules/@earendil-works/pi-coding-agent');
const require=createRequire(join(pkg,'package.json'));
const {createJiti}=require('jiti');
const factory=await createJiti(import.meta.url,{moduleCache:false}).import(resolve('.pi/extensions/recordprep-motion-organization-tools.ts'),{default:true});
globalThis.fetch=()=>{throw new Error('Network forbidden');};
const root=process.env.RECORDPREP_GUARD_TEST_ROOT;
mkdirSync(root,{recursive:true,mode:0o700}); chmodSync(root,0o700);
const candidate=join(root,'candidate.json'), source=join(root,'source-98.txt'), other=join(root,'source-200.txt');
for(const path of [source,other]) writeFileSync(path,'Synthetic motion source',{mode:0o600});
const spec=join(root,'access.json');
function configure(value){writeFileSync(spec,JSON.stringify(value),{mode:0o600});chmodSync(spec,0o600);}
configure({candidate,reads:[source]});
process.env.RECORDPREP_MOTION_ORGANIZATION_ACCESS_SPEC=spec;
function harness(){const handlers={};factory({on:(n,f)=>handlers[n]=f});return (toolName,path)=>handlers.tool_call({toolName,input:{path}},{cwd:root});}
const guard=harness();
assert.equal(await guard('read',source),undefined);
assert.equal(await guard('write',candidate),undefined);
writeFileSync(candidate,'{}',{mode:0o600});
assert.equal(await guard('edit',candidate),undefined);
assert.equal(await guard('read',candidate),undefined);
for(const tool of ['bash','grep','find','ls','codemode','unknown_tool','summary_submit_candidate']) assert.equal((await guard(tool,source)).block,true);
for(const path of [source,other,spec,join(root,'motion_groups.json'),join(root,'motion_boundaries.json'),join(root,'toc.txt'),join(root,'motions_sum.txt')]){
 assert.equal((await guard('write',path)).block,true);assert.equal((await guard('edit',path)).block,true);
}
for(const path of [other,spec,`${root}/../${root.split('/').at(-1)}/source-98.txt`]) assert.equal((await guard('read',path)).block,true);
unlinkSync(candidate);symlinkSync(other,candidate);
assert.equal((await guard('write',candidate)).block,true);assert.equal((await guard('read',candidate)).block,true);
unlinkSync(candidate);linkSync(other,candidate);assert.equal((await guard('write',candidate)).block,true);unlinkSync(candidate);
linkSync(source,join(root,'alias.txt'));assert.equal((await guard('read',source)).block,true);
for(const invalid of [{},{candidate:spec,reads:[source]},{candidate,reads:[join(dirname(root),'outside.txt')]}]){
 configure(invalid);const bad=harness();assert.equal((await bad('read',source)).block,true);assert.equal((await bad('write',candidate)).block,true);
}
console.log('Motion organization boundary contract passed');
