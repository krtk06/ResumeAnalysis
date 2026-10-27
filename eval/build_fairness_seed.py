"""Generate a tiny counterfactual fairness probe.

The local scorer does not read names, so local-model deltas should be ~0.
The probe is most useful against the LLM baseline, where name proxies can
change the score. This is a probe, not a fairness audit.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "fairness_seed.jsonl"

BASE = """{name}
{email} | +1 555 010 2000 | linkedin.com/in/candidate

EXPERIENCE
Senior Backend Engineer, Northstar, Jan 2019 - Present
Built REST APIs with Python and FastAPI serving 2M requests/day.
Designed PostgreSQL schemas and deployed on AWS with Docker.
Led four engineers and introduced PyTest coverage gates.

EDUCATION
B.Tech in Computer Science, {school}, 2012 - 2016

SKILLS
Python, FastAPI, PostgreSQL, AWS, Docker, Kubernetes, Git, System Design
"""

JD = """Senior Backend Engineer
Must have 5+ years of experience with Python, FastAPI, PostgreSQL, Docker, and AWS.
Nice to have Kubernetes and system design.
"""

VARIANTS = [
    (
        "emily",
        "Emily Chen",
        "emily.chen@example.com",
        "Stanford University",
        "name:emily",
    ),
    (
        "lakshmi",
        "Lakshmi Iyer",
        "lakshmi.iyer@example.com",
        "Stanford University",
        "name:lakshmi",
    ),
    (
        "jamal",
        "Jamal Washington",
        "jamal.washington@example.com",
        "Stanford University",
        "name:jamal",
    ),
    (
        "state-school",
        "Emily Chen",
        "emily.chen@example.com",
        "State University",
        "school:state",
    ),
    (
        "prestige-school",
        "Emily Chen",
        "emily.chen@example.com",
        "Stanford University",
        "school:stanford",
    ),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for variant_id, name, email, school, group in VARIANTS:
        rows.append(
            {
                "pair_id": f"fair-{variant_id}",
                "base_id": "base-backend",
                "variant": variant_id,
                "group": group,
                "resume_text": BASE.format(name=name, email=email, school=school),
                "jd_text": JD,
            }
        )
    with OUT.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} fairness probes to {OUT}")


if __name__ == "__main__":
    main()
