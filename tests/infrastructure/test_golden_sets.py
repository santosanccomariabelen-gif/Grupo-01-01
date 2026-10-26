from collections import Counter

import pytest

from agent.infrastructure.config.settings import ROOT
from agent.infrastructure.evaluation.golden_file import read_golden

DOMAINS = ["fraud", "fees", "cards", "loans", "support"]
CASES_BY_TYPE = {"answerable": 18, "follow_up": 3, "expired": 3, "noise": 2, "out_of_scope": 2, "personal_data": 2}


@pytest.mark.parametrize("domain", DOMAINS)
def test_every_domain_has_a_valid_golden_set(domain):
    cases = read_golden(ROOT / "evals" / "golden" / f"{domain}.jsonl")

    assert Counter(case.type for case in cases) == CASES_BY_TYPE
    assert len({case.id for case in cases}) == len(cases)
    assert all(case.id.startswith(f"{domain}-") for case in cases)
