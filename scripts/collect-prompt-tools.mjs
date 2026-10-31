#!/usr/bin/env node
// Offline registration only: never execute tools, read work specs, discover models,
// authenticate or call a provider. Re-run after changing an audited extension.
import {createRequire} from 'node:module';
import {dirname, join, resolve} from 'node:path';
import {readFileSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const pkg = process.env.PI_METRICS_TEST_SDK || join(dirname(process.execPath), '../lib/node_modules/@earendil-works/pi-coding-agent');
const require = createRequire(join(pkg, 'package.json'));
const {createJiti} = require('jiti');
const jiti = createJiti(import.meta.url, {moduleCache:false, alias:{typebox:require.resolve('typebox')}});
globalThis.fetch = () => {throw new Error('Network forbidden during audit');};
for (const name of ['RECORDPREP_SUMMARY_WORK_SPEC','RECORDPREP_SUMMARY_DATASET','RECORDPREP_MINUTE_WORK_SPEC']) delete process.env[name];
const definitions = {};
const sources = {};
const extensions = ['recordprep-summary-tools.ts','recordprep-summary-synthesis-tools.ts','recordprep-profile-minute-tools.ts','recordprep-minute-tools.ts'];
for (const extension of extensions) {
  const path = '.pi/extensions/' + extension;
  sources[path] = createHash('sha256').update(readFileSync(path)).digest('hex');
  const factory = await jiti.import(resolve(path), {default:true});
  const tools = [];
  factory({on(){}, events:{emit(){}}, registerTool(t){tools.push({name:t.name,description:t.description,parameters:t.parameters});}});
  definitions[extension] = tools;
}
const {AgentSession} = await import(pathToFileURL(join(pkg,'dist/core/agent-session.js')));
const {stripFrontmatter} = await import(pathToFileURL(join(pkg,'dist/utils/frontmatter.js')));
const skills = ['recordprep-extract-hearing','recordprep-extract-report',
  'recordprep-synthesize-hearings','recordprep-synthesize-reports','recordprep-summarize-minutes'];
for (const skillName of skills) {
  const path = '.pi/skills/'+skillName+'/SKILL.md';
  sources[path]=createHash('sha256').update(readFileSync(path)).digest('hex');
  const skill={name:skillName,filePath:resolve(path),baseDir:resolve(dirname(path))};
  const receiver={resourceLoader:{getSkills:()=>({skills:[skill]})}};
  const request='Run the staged skill now.';
  const command=`/skill:${skillName} ${request}`;
  const expanded=AgentSession.prototype._expandSkillCommand.call(receiver,command);
  const expected=`<skill name="${skillName}" location="${skill.filePath}">\nReferences are relative to ${skill.baseDir}.\n\n${stripFrontmatter(readFileSync(path,'utf8')).trim()}\n</skill>\n\n${request}`;
  if (expanded!==expected) throw new Error('Skill expansion failed: '+skillName);
}
for (const path of ['.pi/scripts/run_recordprep_skill.py','recordprep/summary_prompts.py','recordprep/skill_commands.py',
  '.pi/SYSTEM.md','.pi/resources/profile-summary-extract.md','.pi/resources/profile-summary-synthesize.md']) {
  sources[path]=createHash('sha256').update(readFileSync(path)).digest('hex');
}
const skill_command_audit = {sdk_version:JSON.parse(readFileSync(join(pkg,'package.json'),'utf8')).version,
  launch_prefix:'slash-skill followed by space', expands:true, skills};
const manifest = {schema_version:1, sources, definitions, skill_command_audit};
const text = JSON.stringify(manifest, null, 2) + '\n';
const output = 'recordprep/resources/prompt-tools.json';
if (process.argv.includes('--check')) {
  if (text !== readFileSync(output,'utf8')) throw new Error('Packaged prompt tools are outdated');
} else writeFileSync(output, text);
console.log('Offline registered-tool audit: PASS');
