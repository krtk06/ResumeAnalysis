"""Build the small, hand-labelled seed set used to smoke-test the eval harness.

This is NOT the final benchmark. The full 300-1000 pair set needs independent
human labels, double-labelling, and adjudication. The seed set exists so the
pipeline, metrics, and report format are executable from day one.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "seed_pairs.jsonl"

RESUMES = {
    "r-backend": """Priya Nair
priya.nair@example.com | +91 98765 43210 | Bengaluru

EXPERIENCE
Senior Backend Engineer, Northstar Systems, Jan 2019 - Present
Designed REST APIs with Python and FastAPI serving 3M requests/day.
Modelled PostgreSQL schemas and cut query latency by 45%.
Deployed services on AWS with Docker, Kubernetes, and GitHub Actions.
Led four engineers and introduced code review and PyTest gates.
Backend Engineer, DataForge, Jun 2016 - Dec 2018
Built event-driven services with Python, Redis, and RabbitMQ.

EDUCATION
B.Tech in Computer Science, NIT Trichy, 2012 - 2016

SKILLS
Python, FastAPI, PostgreSQL, Redis, AWS, Docker, Kubernetes, Terraform, GitHub Actions, PyTest, System Design
""",
    "r-frontend": """Jordan Lee
jordan.lee@example.com | +1 415 555 0199 | San Francisco

EXPERIENCE
Senior Frontend Engineer, Lumen, Feb 2020 - Present
Built a React and TypeScript design system used by 40 engineers.
Improved Core Web Vitals and cut bundle size by 35% with Next.js.
Implemented WCAG 2.1 accessibility fixes and keyboard navigation.
Frontend Engineer, Canvas, Jul 2017 - Jan 2020
Shipped responsive dashboards with React, CSS, and Redux.

EDUCATION
B.S. in Information Systems, University of Washington, 2013 - 2017

SKILLS
JavaScript, TypeScript, React, Next.js, HTML, CSS, Tailwind CSS, Redux, Web Accessibility, Jest, Playwright, Figma
""",
    "r-ml": """Dr. Anika Rao
anika.rao@example.com | +91 99887 76655 | Hyderabad

EXPERIENCE
Machine Learning Engineer, Helix AI, Mar 2019 - Present
Fine-tuned transformer models for document classification with PyTorch.
Built NLP evaluation pipelines and improved macro-F1 by 18%.
Deployed models on AWS with Docker and Kubernetes; added Prometheus monitoring.
Data Scientist, Insight Labs, Aug 2016 - Feb 2019
Built churn models with scikit-learn and ran A/B tests.

EDUCATION
Ph.D. in Computer Science, IIT Hyderabad, 2012 - 2016

SKILLS
Python, PyTorch, TensorFlow, Transformers, NLP, MLOps, Docker, Kubernetes, AWS, Prometheus, Statistics, A/B Testing
""",
    "r-analyst": """Sam Patel
sam.patel@example.com | +1 646 555 0134 | New York

EXPERIENCE
Data Analyst, Retail Co, Apr 2020 - Present
Wrote advanced SQL across PostgreSQL and BigQuery for weekly reporting.
Built Tableau dashboards used by 200+ store managers.
Automated Excel reports with Python and pandas, saving 12 hours/week.
Data Analyst, MarketWorks, Jan 2018 - Mar 2020
Cleaned survey data and presented business metrics to stakeholders.

EDUCATION
B.A. in Economics, Rutgers University, 2013 - 2017

SKILLS
SQL, PostgreSQL, BigQuery, Tableau, Power BI, Excel, Python, Pandas, Statistics, Data Visualization, Reporting
""",
    "r-career": """Maya Chen
maya.chen@example.com | +1 312 555 0177 | Chicago

EXPERIENCE
Customer Support Lead, Bright, Jun 2021 - Present
Resolved escalations and documented recurring product issues.
Built a small Python script to classify support tickets, reducing triage time by 20%.
Completed a React and Node.js bootcamp; shipped a personal dashboard.

EDUCATION
B.A. in Communications, University of Illinois, 2015 - 2019

SKILLS
Python, JavaScript, React, Node.js, SQL, Communication, Problem Solving
""",
    "r-nonresume": """Project Brief: Atlas Data Platform
Scope of Work
The vendor will deliver a data platform, migration plan, and training materials.
Deliverables
1. Architecture document
2. Migration runbook
3. Evaluation focus and acceptance criteria
Payment terms are net 30. This document is not a candidate resume.
""",
}

JDS = {
    "jd-backend": """Senior Backend Engineer — Platform
Must have 5+ years of backend engineering experience.
Required: Python, FastAPI, PostgreSQL, REST API design, Docker, and AWS.
Nice to have: Kubernetes, Terraform, and observability with Prometheus.
You will design services, review code, and mentor engineers.
""",
    "jd-frontend": """Senior Frontend Engineer — Product
Must have 4+ years of frontend experience.
Required: React, TypeScript, Next.js, HTML, CSS, and accessibility.
Nice to have: design systems, Redux, Jest, and Playwright.
You will ship responsive interfaces and improve performance.
""",
    "jd-ml": """Machine Learning Engineer — NLP
Must have 3+ years of applied ML experience.
Required: Python, PyTorch, NLP, model deployment, and Docker.
Nice to have: TensorFlow, Kubernetes, MLOps, and A/B testing.
You will fine-tune models, evaluate them, and ship inference services.
""",
}

# relevance (0-3), holistic score (0-10), is_resume
LABELS = {
    ("r-backend", "jd-backend"): (3, 9.0, True),
    ("r-frontend", "jd-backend"): (1, 3.0, True),
    ("r-ml", "jd-backend"): (2, 6.0, True),
    ("r-analyst", "jd-backend"): (1, 3.0, True),
    ("r-career", "jd-backend"): (1, 2.0, True),
    ("r-nonresume", "jd-backend"): (0, 0.0, False),
    ("r-backend", "jd-frontend"): (1, 3.0, True),
    ("r-frontend", "jd-frontend"): (3, 9.0, True),
    ("r-ml", "jd-frontend"): (0, 1.0, True),
    ("r-analyst", "jd-frontend"): (1, 2.0, True),
    ("r-career", "jd-frontend"): (1, 3.0, True),
    ("r-nonresume", "jd-frontend"): (0, 0.0, False),
    ("r-backend", "jd-ml"): (1, 3.0, True),
    ("r-frontend", "jd-ml"): (0, 1.0, True),
    ("r-ml", "jd-ml"): (3, 9.0, True),
    ("r-analyst", "jd-ml"): (1, 2.0, True),
    ("r-career", "jd-ml"): (0, 1.0, True),
    ("r-nonresume", "jd-ml"): (0, 0.0, False),
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for (resume_id, jd_id), (relevance, holistic, is_resume) in LABELS.items():
        rows.append(
            {
                "pair_id": f"{resume_id}__{jd_id}",
                "resume_id": resume_id,
                "jd_id": jd_id,
                "resume_text": RESUMES[resume_id].strip(),
                "jd_text": JDS[jd_id].strip(),
                "relevance": relevance,
                "holistic_score": holistic,
                "is_resume": is_resume,
            }
        )
    with OUT.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} pairs to {OUT}")


if __name__ == "__main__":
    main()
