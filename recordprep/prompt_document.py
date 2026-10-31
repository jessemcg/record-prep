"""Literal, ordered model-visible components. Never format user-controlled prose."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSection:
    identity: str
    text: str
    slot: str = "fixed"  # fixed / profile / runtime; audit metadata, never sent


@dataclass(frozen=True)
class PromptDocument:
    sections: tuple[PromptSection, ...]
    separator: str = "\n\n"

    def render(self, *, placeholders: bool = False) -> str:
        return self.separator.join(
            ("⟪" + section.identity + "⟫" if placeholders and section.slot != "fixed" else section.text)
            for section in self.sections
        )
