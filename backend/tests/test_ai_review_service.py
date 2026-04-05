from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.schemas import Finding
from app.services.ai_review_service import AIReviewService


@pytest.mark.parametrize(
    ("rule_id", "title", "description", "snippet", "expected_text", "expected_fix"),
    [
        ("import-error", "import-error", "Unable to import 'requests'", "", "pip install requests", "pip install requests"),
        ("no-name-in-module", "no-name-in-module", "No name 'Session' in module 'requests'", "", "from requests import Session", "from requests import Session"),
        ("misplaced-bare-raise", "misplaced-bare-raise", "No active exception to reraise", "", "except Exception as exc", "raise exc"),
        ("not-callable", "not-callable", "'client' is not callable", "", "client", "client"),
        ("unused-variable", "unused-variable", "Unused variable 'response'", "1: response = client.get(url)", "_response", "_response = client.get(url)"),
        ("broad-exception-caught", "broad-exception-caught", "Catching too general exception Exception", "", "except ValueError as exc", "except ValueError as exc"),
        ("too-many-branches", "too-many-branches", "Too many branches (14/12)", "", "dispatch", "handler = handlers.get"),
        ("missing-function-docstring", "missing-function-docstring", "Missing function or method docstring", "", 'docstring', '"""Return the result for risky_fetch. """'),
    ],
)
def test_ai_review_service_generates_rule_specific_guidance(rule_id, title, description, snippet, expected_text, expected_fix):
    service = AIReviewService(get_settings())
    finding = Finding(
        id="ISSUE-0001",
        category="bug",
        title=title,
        description=description,
        file_path="package/service.py",
        start_line=1,
        end_line=1,
        tool_source="pylint",
        rule_id=rule_id,
        symbol_name="risky_fetch",
        symbol_type="function",
        snippet=snippet,
    )

    enriched = service.enrich([finding])[0]

    assert expected_text in enriched.suggestion or expected_text in enriched.fix_patch
    assert expected_fix == enriched.fix_patch or expected_fix in enriched.fix_patch
    assert enriched.impact
    assert enriched.root_cause
    assert 0 <= enriched.confidence <= 100
    assert enriched.fix_effort in {"low", "medium", "high"}
