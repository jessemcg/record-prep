"""Optional passive sibling observer; never load model-facing resources here."""
import importlib.util
from pathlib import Path
import sys


def instrument(command, env, workflow, prefix, *, project=None, app='recordprep'):
    project = Path(project) if project is not None else Path(__file__).resolve().parents[1]
    try:
        helper = project.parent / 'PiRunMetrics' / 'launch_adapter.py'
        spec = importlib.util.spec_from_file_location('_app_run_metrics_adapter', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.instrument(command, env, project, app, workflow, prefix)
    except Exception:
        if env.get('PI_RUN_METRICS_ENABLED') != '0':
            print('Pi run metrics: collection incomplete or unavailable.', file=sys.stderr)
        # Never retain another application's identity on a child launch.
        clean = dict(env)
        for key in ('APP', 'WORKFLOW', 'REVISION', 'DIRTY', 'PI_VERSION'):
            clean.pop('PI_RUN_METRICS_' + key, None)
        return list(command), clean
