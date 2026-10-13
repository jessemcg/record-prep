"""Compatibility preview for historical profile caption resources.

Production inference and freshness live in case_name_stage, independent of profile
prose. Keep old profile schemas readable without migrating stored snapshots.
"""
import hashlib

from .case_name_prompt import CASE_NAME_PROMPT


def compile_case_name(snapshot):
    if snapshot.manifest["schema_version"] == 1:
        return None
    return CASE_NAME_PROMPT, hashlib.sha256(CASE_NAME_PROMPT.encode()).hexdigest()
