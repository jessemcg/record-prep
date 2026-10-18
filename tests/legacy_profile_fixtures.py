"""Explicit legacy-generation coverage, separate from current app selection tests.

Old fixtures intentionally exercise the retained unassigned algorithms and schemas.
Production always resolves application guidance; this test-only injection keeps the
frozen compatibility contracts covered without inventing a production legacy mode.
"""
import sys
from functools import wraps
from unittest.mock import patch


def legacy_profile_tests(cls):
    setup = cls.setUp
    @wraps(setup)
    def setUp(self):
        context = patch("recordprep.case_profiles.resolve_case_profile", return_value=None)
        context.start()
        self.addCleanup(context.stop)
        setup(self)
    cls.setUp = setUp
    return cls


def legacy_runner_argv(runner, *args):
    code = ("import runpy,sys; from unittest.mock import patch; "
            "runner=sys.argv.pop(1); "
            "p=patch('recordprep.case_profiles.resolve_case_profile',return_value=None); "
            "p.start(); runpy.run_path(runner,run_name='__main__')")
    return [sys.executable, "-c", code, str(runner), *args]
