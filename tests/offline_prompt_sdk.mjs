// Capture Pi's final request context using actual skill expansion and extensions.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {join,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import net from 'node:net';
import http from 'node:http';
import https from 'node:https';
const forbidden=()=>{throw new Error('Network forbidden in offline prompt acceptance');};
globalThis.fetch=forbidden; net.connect=forbidden; net.Socket.prototype.connect=forbidden;
http.request=forbidden;http.get=forbidden;https.request=forbidden;https.get=forbidden;
const pkg=process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath),'../lib/node_modules/@earendil-works/pi-coding-agent');
const sdk=await import(pathToFileURL(join(pkg,'dist/index.js')));
const {stripFrontmatter}=await import(pathToFileURL(join(pkg,'dist/utils/frontmatter.js')));
const ai=await import(pathToFileURL(join(pkg,'node_modules/@earendil-works/pi-ai/dist/index.js')));
const plan=JSON.parse(readFileSync(process.argv[2],'utf8'));
const cwd=process.cwd();
const model={id:'synthetic',name:'Synthetic',provider:'prompt-test',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:1000000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let captured;
let calls=0;
const settingsManager=sdk.SettingsManager.inMemory({enableSkillCommands:true,compaction:{enabled:false},retry:{enabled:false}});
const loader=new sdk.DefaultResourceLoader({cwd,agentDir:join(cwd,'agent'),settingsManager,
 noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,
 additionalExtensionPaths:plan.extensions || [plan.extension],additionalSkillPaths:[plan.skill],
 systemPromptOverride:()=>plan.system,
 extensionFactories:[pi=>pi.registerProvider('prompt-test',{...model,apiKey:'synthetic',models:[model],streamSimple(_m,context){
 captured ??= structuredClone(context);
 const frame=plan.frames?.[calls++] || {content:[{type:'text',text:'Offline capture only.'}],stopReason:'stop'};
 const stream=new ai.AssistantMessageEventStream();
 queueMicrotask(()=>{const message={role:'assistant',api:model.api,provider:model.provider,model:model.id,usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},timestamp:0,...frame};stream.push({type:'done',reason:message.stopReason,message});stream.end();});return stream;
 }})]});
await loader.reload();assert.deepEqual(loader.getExtensions().errors,[]);
assert.ok(loader.getSkills().skills.some(s=>s.name===plan.launch.split(/\s/)[0].slice(7)),JSON.stringify(loader.getSkills()));
const runtime=await sdk.ModelRuntime.create({credentials:new ai.InMemoryCredentialStore(),modelsPath:join(cwd,'models.json'),modelsStorePath:join(cwd,'store.json'),allowModelNetwork:false});
const {session}=await sdk.createAgentSession({cwd,agentDir:join(cwd,'agent'),modelRuntime:runtime,model,thinkingLevel:'off',resourceLoader:loader,settingsManager,sessionManager:sdk.SessionManager.inMemory(cwd),tools:plan.tools});
try {
 assert.deepEqual(session.getActiveToolNames().sort(),[...plan.tools].sort());
 if (plan.bindExtensions) await session.bindExtensions({shutdownHandler:()=>{},onError:e=>{throw new Error(JSON.stringify(e));}});
 await session.prompt(plan.launch);assert.ok(captured);
 const user=captured.messages.find(m=>m.role==='user');
 const message=typeof user.content==='string'?user.content:user.content[0].text;
 if (plan.expectExpanded===false) {
  assert.equal(message,plan.launch);
 } else {
  const skill=loader.getSkills().skills.find(s=>s.name===plan.launch.split(' ')[0].slice(7));
  assert.ok(skill,'Exact skill name must match before expansion');
  const body=stripFrontmatter(readFileSync(skill.filePath,'utf8')).trim();
  const args=plan.launch.slice(plan.launch.indexOf(' ')+1).trim();
  assert.equal(message,`<skill name="${skill.name}" location="${skill.filePath}">\nReferences are relative to ${skill.baseDir}.\n\n${body}\n</skill>\n\n${args}`);
 }
 if (plan.bindExtensions) captured.tool_results=session.messages.filter(m=>m.role==='toolResult');
 writeFileSync(process.argv[3],JSON.stringify(captured));
}finally{session.dispose();}
