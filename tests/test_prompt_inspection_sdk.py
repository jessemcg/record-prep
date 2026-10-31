"""No credentials/network: final Pi context includes actual expanded staged skill."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from recordprep.prompt_inspection import inspect_prompt, SUMMARY_TASKS, TOOLS
from test_structured_classification import bundle, ROOT


class PromptSDKTests(unittest.TestCase):
    def test_registered_manifest(self):
        if not shutil.which('node'):self.skipTest('Node unavailable')
        result=subprocess.run(['node','scripts/collect-prompt-tools.mjs','--check'],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_final_application_controlled_context_and_skill_expansion(self):
        if not shutil.which('node'):self.skipTest('Node unavailable')
        for task,_ in SUMMARY_TASKS:
            with self.subTest(task=task),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                inspection=inspect_prompt({k:bundle().resource(k) for k in bundle().manifest['resources']},task,ROOT/'.pi',template=False,snapshot=bundle())
                parts=inspection.components
                skill_name=parts[1][0].split(': ',1)[1]
                skill=root/skill_name/'SKILL.md';skill.parent.mkdir();skill.write_text(parts[1][1])
                phase='minutes' if task=='minutes' else task.split('-')[1]
                extension={'extract':'recordprep-summary-tools.ts','synthesize':'recordprep-summary-synthesis-tools.ts','minutes':'recordprep-profile-minute-tools.ts'}[phase]
                plan={'system':parts[0][1],'skill':str(skill),'extension':str(ROOT/'.pi/extensions'/extension),'tools':list(TOOLS[phase]),'launch':parts[2][1]}
                path=root/'plan.json';path.write_text(json.dumps(plan));capture=root/'capture.json'
                env=os.environ.copy()
                for name in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','TMPDIR'):
                    p=root/name;p.mkdir(mode=0o700);env[name]=str(p)
                for name in ('RECORDPREP_SUMMARY_WORK_SPEC','RECORDPREP_SUMMARY_DATASET','RECORDPREP_MINUTE_WORK_SPEC'):
                    env.pop(name,None)
                result=subprocess.run(['node',str(ROOT/'tests/offline_prompt_sdk.mjs'),str(path),str(capture)],cwd=root,env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                context=json.loads(capture.read_bytes())
                system=next(m for m in context['messages'] if m['role']=='system')
                self.assertIn(parts[0][1].strip(),system['content'] + '\n'.join(v or '' for v in system.get('sections',{}).values()))
                user=next(m for m in context['messages'] if m['role']=='user')
                message=user['content'] if isinstance(user['content'],str) else user['content'][0]['text']
                # The Node harness additionally checks the exact complete skill
                # body plus unchanged arguments in the final provider context.
                self.assertTrue(message.startswith('<skill name="'+skill_name+'"'))
                self.assertEqual(message.count('<skill name='),1)
                self.assertTrue(message.endswith(parts[2][1].split(' ',1)[1].strip()))
                self.assertEqual(inspection.issues,())
                actual={t['name']:{'name':t['name'],'description':t['description'],'parameters':t['parameters']} for t in system['toolsAdded']}
                expected={t['name']:t for t in json.loads(parts[3][1])}
                self.assertEqual(actual,expected)
