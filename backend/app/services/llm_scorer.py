import json
import logging
import os
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a strict, calibrated tech recruiter scoring resumes 0-10.
Rubric: 40% skills/keyword coverage, 30% relevant experience/projects, 20% domain fit, 10% clarity/impact.
Be calibrated: most resumes score 3-6, only strong role-specific resumes score 7+, perfect matches 9+.
If the document is not a resume, is random/unrelated, or has zero relevant skills for the target role, score 0-3 (typically 1-2.5) — do NOT inflate.
Count synonyms fairly (PostgreSQL≈SQL, Next.js≈React) but do not invent relevance that isn't in the text.
You must also classify if the document is a real resume.
Return JSON only with no markdown."""

def _build_user_prompt(resume_text: str, target_role: str, skills: List[str], role_description: str) -> str:
    # Cap resume to ~6000 chars to stay within context/cost
    clipped = resume_text[:6000]
    return (
        f"Target role: {target_role}\n"
        f"Role description: {role_description}\n"
        f"Extracted skills: {', '.join(skills) if skills else 'none'}\n\n"
        f"Resume text:\n{clipped}\n\n"
        "Rules: If the document is not a resume or has no overlap with the target role, you MUST score <3 and explain why it is unrelated. "
        "Do not give 7+ unless there is clear, role-specific evidence in the text.\n"
        "Return JSON with keys: is_resume (boolean true only if this is a real candidate resume with personal experience/education, false for specs, articles, random docs), "
        "score (0-10 float, one decimal), label (one of 'Excellent match','Good match','Moderate match','Needs work'), "
        "reasoning (one sentence why), missing (array of 1-3 short strings of what's missing), "
        "alternative_roles (array of 1-3 objects {role, match 0-1})."
    )

def score_with_openai(
    resume_text: str,
    target_role: str,
    skills: List[str],
    role_description: str,
    model: str | None = None,
) -> Tuple[float, str, List[Dict], List[Dict], bool] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        logger.warning("openai package not installed, skipping LLM scoring")
        return None

    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(resume_text, target_role, skills, role_description)},
            ],
            max_tokens=500,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)

        is_resume = data.get("is_resume", True)
        # Normalize is_resume to bool (LLM sometimes returns string)
        if isinstance(is_resume, str):
            is_resume = is_resume.lower() not in ("false", "no", "0")
        else:
            is_resume = bool(is_resume)

        score = float(data.get("score", 0))
        score = max(0.0, min(10.0, round(score, 1)))

        # Hard guard: random/non-resume docs must not get 7+ even if LLM hallucinates generosity
        if not skills and score > 3.0:
            score = min(score, 2.5)
            logger.warning("LLM returned high score for doc with no extracted skills; capping to %s", score)
        elif len(skills) <= 1 and score >= 6.0:
            score = min(score, 3.5)
            logger.warning("LLM returned high score for doc with <=1 skill; capping to %s", score)

        # Expose is_resume to caller via data dict
        data["_is_resume"] = is_resume

        # Derive label if missing/invalid
        label = str(data.get("label", "")).strip()
        if label not in ("Excellent match", "Good match", "Moderate match", "Needs work"):
            if score >= 8:
                label = "Excellent match"
            elif score >= 6:
                label = "Good match"
            elif score >= 4:
                label = "Moderate match"
            else:
                label = "Needs work"

        reasoning = str(data.get("reasoning", "")).strip()
        missing = data.get("missing", [])
        alt = data.get("alternative_roles", [])

        # Normalize improvements from missing + reasoning
        improvements: List[Dict] = []
        if reasoning:
            improvements.append({"area": reasoning, "priority": "high"})
        for m in (missing or [])[:3]:
            if isinstance(m, str) and m.strip():
                improvements.append({"area": m.strip().title(), "priority": "medium" if len(improvements) >= 2 else "high"})

        # Normalize alt roles
        alt_roles: List[Dict] = []
        for item in (alt or [])[:3]:
            if isinstance(item, dict) and "role" in item:
                try:
                    match = float(item.get("match", 0.6))
                except Exception:
                    match = 0.6
                alt_roles.append({"role": str(item["role"]), "match": round(max(0.0, min(1.0, match)), 2)})

        # Fallback alt_roles if LLM returned none
        if not alt_roles:
            alt_roles = []

        return score, label, alt_roles, improvements, is_resume

    except Exception as e:
        logger.exception("OpenAI scoring failed (model=%s): %s", model, e)
        return None
