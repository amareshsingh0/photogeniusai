"""
Pattern Matcher for Failure Memory & Smart Recovery.
Matches prompts against stored regex/semantic patterns for auto-fix lookup.
P1: 70%+ common failures auto-fixed on first attempt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PatternMatch:
    """Result of matching a prompt against a stored pattern."""

    pattern: str
    failure: str
    fix: Dict[str, Any]
    score: float  # 0–1 match strength
    matched_groups: Tuple[str, ...] = ()


class PatternMatcher:
    """
    Match prompt against stored patterns (regex or keyword).
    Returns best match and applicable fix for smart recovery.
    """

    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive
        self._compiled: Dict[str, re.Pattern] = {}

    def _normalize(self, text: str) -> str:
        return text if self.case_sensitive else text.lower()

    def _compile(self, pattern: str) -> re.Pattern:
        if pattern not in self._compiled:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            try:
                self._compiled[pattern] = re.compile(pattern, flags)
            except re.error:
                # Fallback: treat as literal substring
                escaped = re.escape(pattern)
                self._compiled[pattern] = re.compile(escaped, flags)
        return self._compiled[pattern]

    def match(
        self,
        prompt: str,
        pattern: str,
        failure: str,
        fix: Dict[str, Any],
    ) -> Optional[PatternMatch]:
        """
        Match prompt against one pattern. Returns PatternMatch if match, else None.
        """
        normalized = self._normalize(prompt)
        try:
            compiled = self._compile(pattern)
            m = compiled.search(normalized)
            if m is None:
                return None
            groups = m.groups() if m.lastindex else ()
            # Score: full match = 1.0; partial by length ratio
            score = min(1.0, 0.5 + 0.5 * (m.end() - m.start()) / max(1, len(normalized)))
            return PatternMatch(
                pattern=pattern,
                failure=failure,
                fix=fix,
                score=score,
                matched_groups=groups,
            )
        except Exception:
            return None

    def best_match(
        self,
        prompt: str,
        patterns: List[Dict[str, Any]],
    ) -> Optional[PatternMatch]:
        """
        Find best matching pattern from list of {pattern, failure, fix}.
        Returns highest-score match or None.
        """
        best: Optional[PatternMatch] = None
        for p in patterns:
            pat = p.get("pattern") or p.get("pattern_regex")
            failure = p.get("failure", "")
            fix = p.get("fix") or p.get("fix_params") or {}
            if not pat:
                continue
            m = self.match(prompt, pat, failure, fix)
            if m and (best is None or m.score > best.score):
                best = m
        return best

    def match_keywords(self, prompt: str, keywords: List[str]) -> float:
        """
        Return match score 0–1 based on how many keywords appear in prompt.
        """
        normalized = self._normalize(prompt)
        if not keywords:
            return 0.0
        found = sum(1 for k in keywords if self._normalize(k) in normalized)
        return found / len(keywords)
