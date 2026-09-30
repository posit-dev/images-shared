import json
import re
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.model import ChatMessageUser, get_model
from inspect_ai.scorer import Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState, generate, system_message

_SKILL_MD = (Path(__file__).resolve().parent.parent / "SKILL.md").read_text()

SYSTEM_PROMPT = f"""\
You are a developer working in a Posit container image repository. The repositories \
follow a specific set of rules for building and managing images with the bakery CLI.

Follow the guidance in the bakery skill below to answer questions about how to \
complete tasks in these repositories. Be specific: name the exact commands, flags, \
and files involved. Do not skip steps.

---
{_SKILL_MD}
"""

_GRADER_PROMPT = """\
You are grading a response about how to use the bakery CLI. Compare the response \
against the checklist below and return a JSON evaluation.

## Response to grade

{submission}

## Checklist

### Expected behaviors (response SHOULD include these)
{expected_text}

### Forbidden behaviors (response MUST NOT include these)
{forbidden_text}

## Instructions

For each expected behavior, respond "YES" if the response includes it \
(even if phrased differently), or "NO" if it is missing.

For each forbidden behavior, respond "ABSENT" if the response correctly avoids it, \
or "PRESENT" if the response recommends or implies it.

Return ONLY a JSON object in this exact format (no markdown fences, no extra text):
{{"expected": {{{expected_template}}}, \
"forbidden": {{{forbidden_template}}}, \
"reasoning": "one sentence summary"}}"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from grader output: {text[:200]}")


def _score_from_results(
    expected: dict[str, str],
    forbidden: dict[str, str],
    reasoning: str,
    target_obj: dict,
) -> Score:
    found = sum(1 for v in expected.values() if v.upper() == "YES")
    total = len(expected)
    violations = sum(1 for v in forbidden.values() if v.upper() == "PRESENT")

    if total == 0:
        score_pct = 1.0 if violations == 0 else 0.0
    else:
        score_pct = max(0.0, min(1.0, (found - violations) / total))

    if score_pct >= 0.9:
        grade = "C"
    elif score_pct >= 0.5:
        grade = "P"
    else:
        grade = "I"

    return Score(
        value=grade,
        explanation=reasoning,
        metadata={
            "found": found,
            "total": total,
            "forbidden_triggered": violations,
            "score_pct": round(score_pct, 3),
            "expected": expected,
            "forbidden": forbidden,
            "expected_descriptions": {
                str(v["id"]): v["description"] for v in target_obj.get("expected", [])
            },
            "forbidden_descriptions": {
                str(v["id"]): v["description"] for v in target_obj.get("forbidden", [])
            },
        },
    )


@scorer(metrics=[accuracy(), stderr()])
def behavior_scorer(model: str | None = None):
    async def score(state: TaskState, target: Target) -> Score:
        target_obj = json.loads(target.text)
        expected = target_obj.get("expected", [])
        forbidden = target_obj.get("forbidden", [])

        if expected:
            expected_text = "\n".join(
                f"{v['id']}. {v['description']}" for v in expected
            )
            expected_template = ", ".join(f'"{v["id"]}": "YES or NO"' for v in expected)
        else:
            expected_text = "(none)"
            expected_template = ""

        if forbidden:
            forbidden_text = "\n".join(
                f"{v['id']}. {v['description']}" for v in forbidden
            )
            forbidden_template = ", ".join(
                f'"{v["id"]}": "ABSENT or PRESENT"' for v in forbidden
            )
        else:
            forbidden_text = "(none)"
            forbidden_template = ""

        prompt = _GRADER_PROMPT.format(
            submission=state.output.completion,
            expected_text=expected_text,
            forbidden_text=forbidden_text,
            expected_template=expected_template,
            forbidden_template=forbidden_template,
        )

        grader_model = get_model(model)
        result = await grader_model.generate([ChatMessageUser(content=prompt)])

        try:
            parsed = _extract_json(result.completion)
        except ValueError:
            return Score(
                value="I",
                explanation=f"Grader JSON parse failed: {result.completion[:200]}",
            )

        e_results = parsed.get("expected", {})
        f_results = parsed.get("forbidden", {})
        reasoning = parsed.get("reasoning", "")

        for v in expected:
            e_results.setdefault(str(v["id"]), "NO")
        for v in forbidden:
            f_results.setdefault(str(v["id"]), "ABSENT")

        return _score_from_results(e_results, f_results, reasoning, target_obj)

    return score


@task
def bakery_skill_eval() -> Task:
    return Task(
        dataset=json_dataset("dataset.json"),
        solver=[system_message(SYSTEM_PROMPT), generate(cache_prompt=True)],
        scorer=behavior_scorer(),
    )
