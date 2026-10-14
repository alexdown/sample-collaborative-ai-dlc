#!/usr/bin/env python3
"""File-native AI-DLC workflow state machine for KiroCrew.

No AWS service or custom UI is required. KiroCrew remains the interaction and
agent-dispatch surface; this script owns deterministic stage state and receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN_VERSION = "collaborative-aidlc-83ed7a8-v1"
QUESTION_SUFFIX = "-questions"
INIT = {"workspace-scaffold", "workspace-detection", "state-init"}
LANE_STAGE_IDS = [
    "functional-design",
    "nfr-requirements",
    "nfr-design",
    "infrastructure-design",
    "code-generation",
]
RUNTIME_AGENTS = {
    "aidlc-architect-agent": "collaborative-aidlc-architect",
    "aidlc-architecture-reviewer-agent": "collaborative-aidlc-architecture-reviewer",
    "aidlc-aws-platform-agent": "collaborative-aidlc-aws-platform",
    "aidlc-compliance-agent": "collaborative-aidlc-compliance",
    "aidlc-delivery-agent": "collaborative-aidlc-delivery",
    "aidlc-design-agent": "collaborative-aidlc-design",
    "aidlc-developer-agent": "collaborative-aidlc-developer",
    "aidlc-devsecops-agent": "collaborative-aidlc-devsecops",
    "aidlc-operations-agent": "collaborative-aidlc-operations",
    "aidlc-pipeline-deploy-agent": "collaborative-aidlc-pipeline-deploy",
    "aidlc-product-agent": "collaborative-aidlc-product",
    "aidlc-product-lead-agent": "collaborative-aidlc-product-reviewer",
    "aidlc-quality-agent": "collaborative-aidlc-quality",
}

# Derived from awslabs/aidlc-workflows@83ed7a812c4024904f2c5e4d744e28077e0a5acd
# through this repository's block mapper. The pinned 25-stage profile deliberately
# begins from a supplied intent rather than running Ideation.
PLAN = [
    {"id":"workspace-scaffold","phase":"initialization","lead":"orchestrator"},
    {"id":"workspace-detection","phase":"initialization","lead":"orchestrator"},
    {"id":"state-init","phase":"initialization","lead":"orchestrator"},
    {"id":"reverse-engineering","phase":"inception","lead":"aidlc-developer-agent","support":["aidlc-architect-agent"],"outputs":["business-overview","architecture","code-structure","api-documentation","component-inventory","technology-stack","dependencies","code-quality-assessment","reverse-engineering-timestamp"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"practices-discovery","phase":"inception","lead":"aidlc-pipeline-deploy-agent","support":["aidlc-quality-agent","aidlc-developer-agent","aidlc-devsecops-agent"],"outputs":["team-practices","discovered-rules","evidence","practices-discovery-timestamp"],"consumes":["code-structure","technology-stack","dependencies","code-quality-assessment","architecture","business-overview"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"requirements-analysis","phase":"inception","lead":"aidlc-product-agent","reviewer":"aidlc-product-lead-agent","outputs":["requirements","requirements-analysis-questions"],"consumes":["intent-statement","scope-document","business-overview","architecture","code-structure","team-practices"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"user-stories","phase":"inception","lead":"aidlc-product-agent","support":["aidlc-design-agent"],"reviewer":"aidlc-product-lead-agent","outputs":["stories","personas","user-stories-assessment"],"consumes":["requirements","business-overview","component-inventory","team-practices"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"refined-mockups","phase":"inception","lead":"aidlc-design-agent","support":["aidlc-product-agent"],"reviewer":"aidlc-product-lead-agent","outputs":["mockups","interaction-spec","design-system-mapping","accessibility-checklist","refined-mockups-questions"],"consumes":["wireframes","user-flow","stories","requirements","team-practices"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"application-design","phase":"inception","lead":"aidlc-architect-agent","support":["aidlc-aws-platform-agent","aidlc-design-agent"],"reviewer":"aidlc-architecture-reviewer-agent","outputs":["components","component-methods","services","component-dependency","decisions"],"consumes":["requirements","stories","architecture","component-inventory","team-practices"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"units-generation","phase":"inception","lead":"aidlc-architect-agent","support":["aidlc-delivery-agent"],"reviewer":"aidlc-architecture-reviewer-agent","outputs":["unit-of-work","unit-of-work-dependency","unit-of-work-story-map"],"consumes":["components","component-methods","services","component-dependency","decisions","requirements","stories"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"delivery-planning","phase":"inception","lead":"aidlc-delivery-agent","support":["aidlc-architect-agent"],"outputs":["bolt-plan","team-allocation","risk-and-sequencing-rationale","external-dependency-map","delivery-planning-questions"],"consumes":["requirements","stories","mockups","components","unit-of-work","unit-of-work-dependency","unit-of-work-story-map","team-practices"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"functional-design","phase":"construction","lead":"aidlc-architect-agent","support":["aidlc-developer-agent"],"reviewer":"aidlc-architecture-reviewer-agent","for_each":"unit-of-work","outputs":["business-logic-model","business-rules","domain-entities"],"optional_outputs":["frontend-components"],"consumes":["unit-of-work","unit-of-work-story-map","requirements","components","component-methods","services"],"sensors":["required-sections","upstream-coverage","linter","type-check"]},
    {"id":"nfr-requirements","phase":"construction","lead":"aidlc-architect-agent","support":["aidlc-devsecops-agent","aidlc-compliance-agent","aidlc-quality-agent"],"reviewer":"aidlc-architecture-reviewer-agent","for_each":"unit-of-work","outputs":["performance-requirements","security-requirements","scalability-requirements","reliability-requirements","tech-stack-decisions"],"consumes":["business-logic-model","business-rules","requirements","technology-stack"],"sensors":["required-sections","upstream-coverage","linter","type-check"]},
    {"id":"nfr-design","phase":"construction","lead":"aidlc-architect-agent","support":["aidlc-aws-platform-agent"],"reviewer":"aidlc-architecture-reviewer-agent","for_each":"unit-of-work","outputs":["performance-design","security-design","scalability-design","reliability-design","logical-components"],"consumes":["performance-requirements","security-requirements","scalability-requirements","reliability-requirements","tech-stack-decisions","business-logic-model"],"sensors":["required-sections","upstream-coverage","linter","type-check"]},
    {"id":"infrastructure-design","phase":"construction","lead":"aidlc-aws-platform-agent","support":["aidlc-devsecops-agent","aidlc-compliance-agent"],"reviewer":"aidlc-architecture-reviewer-agent","for_each":"unit-of-work","outputs":["deployment-architecture","infrastructure-services","monitoring-design","cicd-pipeline"],"optional_outputs":["shared-infrastructure"],"consumes":["performance-design","security-design","scalability-design","reliability-design","logical-components","components","services","business-logic-model"],"sensors":["required-sections","upstream-coverage","linter","type-check"]},
    {"id":"code-generation","phase":"construction","lead":"aidlc-developer-agent","reviewer":"aidlc-architecture-reviewer-agent","for_each":"unit-of-work","outputs":["code-generation-plan","code-summary"],"consumes":["business-logic-model","business-rules","domain-entities","performance-design","security-design","deployment-architecture","unit-of-work","requirements"],"sensors":["linter","type-check"]},
    {"id":"build-and-test","phase":"construction","lead":"aidlc-quality-agent","support":["aidlc-devsecops-agent"],"outputs":["build-instructions","unit-test-instructions","integration-test-instructions","performance-test-instructions","security-test-instructions","build-and-test-summary","build-test-results"],"consumes":["code-generation-plan","code-summary"],"sensors":["required-sections","upstream-coverage","type-check"]},
    {"id":"ci-pipeline","phase":"construction","lead":"aidlc-pipeline-deploy-agent","outputs":["ci-config","quality-gates","ci-pipeline-questions"],"consumes":["code-summary","build-and-test-summary","build-test-results"],"sensors":["required-sections","upstream-coverage","linter","type-check"]},
    {"id":"deployment-pipeline","phase":"operation","lead":"aidlc-pipeline-deploy-agent","outputs":["cd-config","deployment-strategy","rollback-runbook","deployment-pipeline-questions"],"consumes":["ci-config","quality-gates","deployment-architecture","cicd-pipeline"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"environment-provisioning","phase":"operation","lead":"aidlc-aws-platform-agent","support":["aidlc-devsecops-agent","aidlc-compliance-agent"],"outputs":["environment-inventory","validation-report","environment-provisioning-questions"],"consumes":["deployment-architecture","infrastructure-services","cd-config"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"deployment-execution","phase":"operation","lead":"aidlc-pipeline-deploy-agent","support":["aidlc-developer-agent"],"outputs":["deployment-log","smoke-test-results","health-check-report","deployment-execution-questions"],"consumes":["cd-config","deployment-strategy","environment-inventory","build-test-results"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"observability-setup","phase":"operation","lead":"aidlc-operations-agent","outputs":["dashboards","alarms","slo-config","log-queries","tracing-config","anomaly-config","observability-setup-questions"],"consumes":["performance-design","security-design","reliability-design","monitoring-design","infrastructure-services"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"incident-response","phase":"operation","lead":"aidlc-operations-agent","outputs":["runbooks","incident-plan","escalation-matrix","incident-response-questions"],"consumes":["dashboards","alarms","reliability-design","security-design","deployment-architecture"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"performance-validation","phase":"operation","lead":"aidlc-quality-agent","outputs":["load-test-plan","load-test-results","nfr-validation-matrix","performance-validation-questions"],"consumes":["performance-requirements","scalability-requirements","performance-design","scalability-design","dashboards"],"sensors":["required-sections","upstream-coverage"]},
    {"id":"feedback-optimization","phase":"operation","lead":"aidlc-operations-agent","support":["aidlc-aws-platform-agent"],"outputs":["slo-report","cost-analysis","drift-report","feedback-loop","feedback-optimization-questions"],"consumes":["dashboards","alarms","slo-config","deployment-log","load-test-results","incident-plan"],"sensors":["required-sections","upstream-coverage"]},
]

PLAN_BY_ID = {stage["id"]: stage for stage in PLAN}
POST_LANE_START = next(i for i, stage in enumerate(PLAN) if stage["id"] == "build-and-test")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:48] or "workflow-intent"


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(value, encoding="utf-8")
    temp.replace(path)


def active_intent(project: Path) -> Path:
    pointer = project / "aidlc" / "active-space"
    if not pointer.exists():
        raise SystemExit("No active workflow. Run `workflow.py init` first.")
    space = pointer.read_text(encoding="utf-8").strip()
    intent_pointer = project / "aidlc" / "spaces" / space / "intents" / "active-intent"
    if not intent_pointer.exists():
        raise SystemExit(f"Space {space!r} has no active intent.")
    rel = intent_pointer.read_text(encoding="utf-8").strip()
    root = project / "aidlc" / "spaces" / space / "intents" / rel
    if not root.is_dir():
        raise SystemExit(f"Active intent directory is missing: {root}")
    return root


def state_path(project: Path) -> Path:
    return active_intent(project) / "workflow-state.json"


def load_state(project: Path) -> tuple[Path, dict[str, Any]]:
    root = active_intent(project)
    return root, json.loads((root / "workflow-state.json").read_text(encoding="utf-8"))


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["updatedAt"] = now()
    state.pop("stateDigest", None)
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    state["stateDigest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    atomic_json(root / "workflow-state.json", state)
    (root / "aidlc-state.md").write_text(render_markdown(state), encoding="utf-8")


def audit(root: Path, event: str, **detail: Any) -> None:
    path = root / "audit" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": now(), "event": event, **detail}, sort_keys=True) + "\n")


def stage_record(state: dict[str, Any], stage_id: str, unit: str | None) -> dict[str, Any]:
    stage = PLAN_BY_ID.get(stage_id)
    if not stage:
        raise SystemExit(f"Unknown stage: {stage_id}")
    if stage.get("for_each"):
        if not unit or unit not in state["units"]:
            raise SystemExit(f"Stage {stage_id} requires --unit naming a registered unit.")
        return state["units"][unit]["stages"][stage_id]
    if unit:
        raise SystemExit(f"Stage {stage_id} is not per-unit; omit --unit.")
    return state["stages"][stage_id]


def unit_complete(unit: dict[str, Any]) -> bool:
    return all(unit["stages"][stage_id]["status"] == "approved" for stage_id in LANE_STAGE_IDS)


def current_work(state: dict[str, Any]) -> list[dict[str, Any]]:
    for stage in PLAN[:11]:
        if state["stages"][stage["id"]]["status"] != "approved":
            return [{"stage": stage["id"], "unit": None}]
    if not state["units"]:
        return [{"stage": "units-generation", "unit": None, "blocked": "register units first"}]
    incomplete = {name for name, unit in state["units"].items() if not unit_complete(unit)}
    if incomplete:
        skeleton = state["walkingSkeleton"]
        if skeleton in incomplete and not unit_complete(state["units"][skeleton]):
            candidates = [skeleton]
        else:
            candidates = sorted(
                name
                for name in incomplete
                if all(dep not in incomplete for dep in state["units"][name]["dependsOn"])
            )
        result = []
        for name in candidates:
            unit = state["units"][name]
            next_stage = next(
                stage_id
                for stage_id in LANE_STAGE_IDS
                if unit["stages"][stage_id]["status"] != "approved"
            )
            result.append({"stage": next_stage, "unit": name})
        return result
    for stage in PLAN[POST_LANE_START:]:
        if state["stages"][stage["id"]]["status"] != "approved":
            return [{"stage": stage["id"], "unit": None}]
    return []


def artifact_dir(root: Path, stage: dict[str, Any], unit: str | None) -> Path:
    if unit:
        return root / "construction" / unit / stage["id"]
    return root / stage["phase"] / stage["id"]


def required_outputs(stage: dict[str, Any]) -> list[str]:
    return [name for name in stage.get("outputs", []) if not name.endswith(QUESTION_SUFFIX)]


def dependency_units(state: dict[str, Any], unit: str) -> set[str]:
    allowed = {unit}
    queue = list(state.get("units", {}).get(unit, {}).get("dependsOn", []))
    while queue:
        dependency = queue.pop()
        if dependency in allowed:
            continue
        allowed.add(dependency)
        queue.extend(state.get("units", {}).get(dependency, {}).get("dependsOn", []))
    return allowed


def find_inputs(
    root: Path, stage: dict[str, Any], unit: str | None, state: dict[str, Any]
) -> dict[str, list[str]]:
    found = {}
    allowed_units = dependency_units(state, unit) if unit else None
    for name in stage.get("consumes", []):
        matches = []
        for path in root.rglob(f"{name}.md"):
            relative = path.relative_to(root)
            if allowed_units is not None and relative.parts[:1] == ("construction",):
                if len(relative.parts) < 2 or relative.parts[1] not in allowed_units:
                    continue
            matches.append(str(relative))
        found[name] = sorted(matches)
    return found


def validate_outputs(root: Path, stage: dict[str, Any], unit: str | None) -> list[dict[str, str]]:
    findings = []
    base = artifact_dir(root, stage, unit)
    for name in required_outputs(stage):
        path = base / f"{name}.md"
        if not path.exists():
            findings.append({"code": "required_artifact_missing", "artifact": name, "path": str(path)})
            continue
        headings = set(re.findall(r"^##\s+.+$", path.read_text(encoding="utf-8"), flags=re.MULTILINE))
        if len(headings) < 2:
            findings.append({"code": "required_sections", "artifact": name, "path": str(path)})
    return findings


def parse_unit_dag(text: str) -> tuple[list[dict[str, Any]], list[list[str]]]:
    match = re.search(r"```ya?ml\s*\n(?P<body>.*?^```)", text, flags=re.MULTILINE | re.DOTALL)
    if not match or not re.search(r"^\s*units\s*:\s*$", match.group("body"), flags=re.MULTILINE):
        raise ValueError("no fenced YAML block with a top-level units: list")
    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in match.group("body").splitlines():
        line = raw.strip()
        if not line or line == "units:" or line == "```":
            continue
        name_match = re.match(r"-\s+name\s*:\s*['\"]?([^'\"]+)['\"]?$", line)
        if name_match:
            if current:
                units.append(current)
            current = {"name": slugify(name_match.group(1)), "dependsOn": []}
            continue
        dep_match = re.match(r"depends_on\s*:\s*\[(.*?)\]\s*$", line)
        if dep_match and current:
            current["dependsOn"] = [slugify(v.strip(" '\"")) for v in dep_match.group(1).split(",") if v.strip()]
            continue
        kind_match = re.match(r"kind\s*:\s*([a-z-]+)$", line)
        if kind_match and current:
            current["kind"] = kind_match.group(1)
            continue
        raise ValueError(f"unsupported units block line: {line}")
    if current:
        units.append(current)
    names = [unit["name"] for unit in units]
    if not names or len(names) != len(set(names)):
        raise ValueError("units must be non-empty and have unique names")
    known = set(names)
    for unit in units:
        for dep in unit["dependsOn"]:
            if dep == unit["name"] or dep not in known:
                raise ValueError(f"invalid dependency {unit['name']} -> {dep}")
    remaining = set(names)
    batches = []
    while remaining:
        ready = sorted(name for name in remaining if all(dep not in remaining for dep in next(u for u in units if u["name"] == name)["dependsOn"]))
        if not ready:
            raise ValueError("unit dependency cycle detected")
        batches.append(ready)
        remaining.difference_update(ready)
    return units, batches


def render_markdown(state: dict[str, Any]) -> str:
    work = current_work(state)
    lines = [
        "# AI-DLC State Tracking",
        "",
        "## Project Information",
        f"- **Project**: {state['title']}",
        f"- **Project Type**: {state['projectType']}",
        "- **Profile**: collaborative-aidlc",
        "- **State Version**: 7",
        f"- **Plan Version**: {state['planVersion']}",
        f"- **Status**: {'Completed' if not work else 'Running'}",
        "",
        "## Current Work",
    ]
    lines.extend([f"- `{item['stage']}`" + (f" for `{item['unit']}`" if item.get("unit") else "") for item in work] or ["- Workflow complete"])
    lines.extend(["", "## Stage Progress"])
    for stage in PLAN:
        if stage.get("for_each"):
            if not state["units"]:
                marker = " "
                detail = "awaiting units"
            else:
                records = [unit["stages"][stage["id"]] for unit in state["units"].values()]
                marker = "x" if all(r["status"] == "approved" for r in records) else "-"
                detail = ", ".join(f"{name}:{state['units'][name]['stages'][stage['id']]['status']}" for name in sorted(state["units"]))
        else:
            status = state["stages"][stage["id"]]["status"]
            marker = "x" if status == "approved" else "?" if status == "awaiting_approval" else "R" if status == "revising" else "-" if status == "running" else " "
            detail = status
        lines.append(f"- [{marker}] {stage['id']} — {detail}")
    return "\n".join(lines) + "\n"


def cmd_init(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    intent = args.intent or (
        Path(args.intent_file).read_text(encoding="utf-8") if args.intent_file else ""
    )
    if not intent.strip():
        raise SystemExit("Provide --intent or --intent-file. The pinned profile begins from a concrete intent.")
    space = slugify(args.space)
    intent_slug = datetime.now().strftime("%y%m%d") + "-" + slugify(args.title)
    root = project / "aidlc" / "spaces" / space / "intents" / intent_slug
    if root.exists():
        raise SystemExit(f"Intent already exists: {root}")
    root.mkdir(parents=True)
    records = {stage["id"]: {"status": "approved" if stage["id"] in INIT else "pending", "attempt": 0, "revision": 0} for stage in PLAN if not stage.get("for_each")}
    state = {
        "schemaVersion": 1,
        "owner": "collaborative-aidlc-kirocrew",
        "stateVersion": 7,
        "planVersion": PLAN_VERSION,
        "title": args.title,
        "intent": intent.strip(),
        "projectType": args.project_type,
        "scope": "collaborative-aidlc",
        "createdAt": now(),
        "updatedAt": now(),
        "status": "running",
        "stages": records,
        "units": {},
        "unitBatches": [],
        "walkingSkeleton": None,
        "receipts": [],
        "reviews": [],
    }
    (root / "intent.md").write_text(f"# {args.title}\n\n{intent.strip()}\n", encoding="utf-8")
    save_state(root, state)
    audit(root, "WORKFLOW_STARTED", profile="collaborative-aidlc", planVersion=PLAN_VERSION)
    marker_path = project / "aidlc" / ".kirocrew-collaborative-aidlc.json"
    prior_marker = marker_path.read_text(encoding="utf-8") if marker_path.exists() else None
    atomic_json(
        marker_path,
        {"owner": "collaborative-aidlc-kirocrew", "planVersion": PLAN_VERSION},
    )
    pointer = project / "aidlc" / "spaces" / space / "intents" / "active-intent"
    prior_pointer = pointer.read_text(encoding="utf-8") if pointer.exists() else None
    try:
        atomic_text(pointer, intent_slug + "\n")
        atomic_text(project / "aidlc" / "active-space", space + "\n")
    except OSError:
        if prior_pointer is None:
            pointer.unlink(missing_ok=True)
        else:
            atomic_text(pointer, prior_pointer)
        if prior_marker is None:
            marker_path.unlink(missing_ok=True)
        else:
            atomic_text(marker_path, prior_marker)
        shutil.rmtree(root, ignore_errors=True)
        raise
    print(root)


def cmd_status(args: argparse.Namespace) -> None:
    root, state = load_state(Path(args.project).resolve())
    payload = {"intentRoot": str(root), "status": "completed" if not current_work(state) else "running", "current": current_work(state), "units": state["units"], "planVersion": state["planVersion"]}
    print(json.dumps(payload, indent=2) if args.json else render_markdown(state))


def cmd_context(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve()
    root, state = load_state(project)
    stage = PLAN_BY_ID.get(args.stage)
    if not stage:
        raise SystemExit(f"Unknown stage: {args.stage}")
    requested = {"stage": args.stage, "unit": args.unit}
    allowed = [
        {"stage": item["stage"], "unit": item.get("unit")}
        for item in current_work(state)
        if not item.get("blocked")
    ]
    if requested not in allowed:
        raise SystemExit(f"Cannot build context for out-of-order work {requested}; current work is {allowed}")
    record = stage_record(state, args.stage, args.unit)
    if record["status"] not in {"pending", "revising"}:
        raise SystemExit(f"Context is available only before dispatch; {args.stage} is {record['status']}")
    base = artifact_dir(root, stage, args.unit)
    base.mkdir(parents=True, exist_ok=True)
    available_inputs = find_inputs(root, stage, args.unit, state)
    project_inputs = {
        name: [str((root / relative).relative_to(project)) for relative in paths]
        for name, paths in available_inputs.items()
    }
    payload = {
        "intent": state["intent"], "projectType": state["projectType"], "stage": stage,
        "runtimeLead": RUNTIME_AGENTS.get(stage["lead"], stage["lead"]),
        "runtimeSupport": [RUNTIME_AGENTS.get(agent, agent) for agent in stage.get("support", [])],
        "runtimeReviewer": RUNTIME_AGENTS.get(stage.get("reviewer"), stage.get("reviewer")) if stage.get("reviewer") else None,
        "unit": args.unit, "attempt": record["attempt"], "revision": record["revision"],
        "feedback": record.get("feedback"),
        "projectRoot": ".",
        "intentRoot": str(root.relative_to(project)),
        "artifactDirectory": str(base.relative_to(project)),
        "requiredArtifactFiles": [
            str((base / f"{name}.md").relative_to(project)) for name in required_outputs(stage)
        ],
        "availableInputs": project_inputs,
        "instruction": "Perform only this stage. Write every required artifact with at least two ## sections. Cite consumed artifacts by exact slug or [[wikilink]]. Do not advance workflow state; the conductor owns transitions.",
    }
    print(json.dumps(payload, indent=2))


def cmd_start(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    requested = {"stage": args.stage, "unit": args.unit}
    allowed = [{"stage": item["stage"], "unit": item.get("unit")} for item in current_work(state) if not item.get("blocked")]
    if requested not in allowed:
        raise SystemExit(f"Cannot start out-of-order work {requested}; current work is {allowed}")
    record = stage_record(state, args.stage, args.unit)
    if record["status"] not in {"pending", "revising"}:
        raise SystemExit(f"Cannot start {args.stage}: status is {record['status']}")
    if record["status"] == "revising":
        for key in ("review", "findings", "evidence", "completedAt"):
            record.pop(key, None)
    record["status"] = "running"; record["attempt"] += 1; record["startedAt"] = now()
    save_state(root, state); audit(root, "STAGE_STARTED", stage=args.stage, unit=args.unit, attempt=record["attempt"])


def cmd_finish(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    stage = PLAN_BY_ID.get(args.stage); record = stage_record(state, args.stage, args.unit)
    if record["status"] != "running":
        raise SystemExit(f"Cannot finish {args.stage}: status is {record['status']}")
    findings = validate_outputs(root, stage, args.unit)
    record["status"] = "awaiting_approval"; record["findings"] = findings; record["completedAt"] = now()
    if args.evidence: record["evidence"] = args.evidence
    save_state(root, state); audit(root, "STAGE_COMPLETED", stage=args.stage, unit=args.unit, findings=findings)
    print(json.dumps({"awaitingApproval": True, "findings": findings}, indent=2))


def cmd_requeue(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    record = stage_record(state, args.stage, args.unit)
    if record["status"] != "running":
        raise SystemExit(f"Cannot requeue {args.stage}: status is {record['status']}")
    if not (args.reason or "").strip():
        raise SystemExit("--reason is required when requeuing remote work.")
    record["status"] = "revising"
    record["revision"] += 1
    record["feedback"] = args.reason.strip()
    for key in ("review", "findings", "evidence", "completedAt"):
        record.pop(key, None)
    save_state(root, state)
    audit(
        root,
        "STAGE_REQUEUED",
        stage=args.stage,
        unit=args.unit,
        attempt=record["attempt"],
        revision=record["revision"],
        reason=record["feedback"],
    )


def cmd_review(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    stage = PLAN_BY_ID.get(args.stage)
    record = stage_record(state, args.stage, args.unit)
    if not stage or not stage.get("reviewer"):
        raise SystemExit(f"Stage {args.stage} has no declared reviewer")
    if record["status"] != "awaiting_approval":
        raise SystemExit(f"Cannot review {args.stage}: status is {record['status']}")
    review = {
        "stage": args.stage,
        "unit": args.unit,
        "attempt": record["attempt"],
        "revision": record["revision"],
        "verdict": args.verdict,
        "findings": args.findings or "",
        "reviewedAt": now(),
    }
    record["review"] = review
    state.setdefault("reviews", []).append(review)
    save_state(root, state); audit(root, "REVIEW_RECORDED", stage=args.stage, unit=args.unit, verdict=args.verdict, attempt=record["attempt"], revision=record["revision"])


def cmd_set_units(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    units_record = state["stages"]["units-generation"]
    if units_record["status"] != "awaiting_approval":
        raise SystemExit("Register units only after units-generation finishes and awaits approval.")
    units, batches = parse_unit_dag(Path(args.artifact).read_text(encoding="utf-8"))
    skeleton = slugify(args.walking_skeleton) if args.walking_skeleton else batches[0][0]
    if skeleton not in set(batches[0]):
        raise SystemExit(
            f"Walking skeleton {skeleton!r} must have no dependencies and belong to the first DAG batch."
        )
    state["units"] = {
        unit["name"]: {**unit, "stages": {stage_id: {"status": "pending", "attempt": 0, "revision": 0} for stage_id in LANE_STAGE_IDS}}
        for unit in units
    }
    state["unitBatches"] = batches; state["walkingSkeleton"] = skeleton
    save_state(root, state); audit(root, "UNIT_PLAN_REGISTERED", units=units, batches=batches, walkingSkeleton=skeleton)
    print(json.dumps({"units": units, "batches": batches, "walkingSkeleton": skeleton}, indent=2))


def cmd_gate(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    record = stage_record(state, args.stage, args.unit)
    if record["status"] != "awaiting_approval":
        raise SystemExit(f"Cannot decide gate for {args.stage}: status is {record['status']}")
    if args.stage == "units-generation" and args.decision != "request-changes" and not state["units"]:
        raise SystemExit("Register the approved unit DAG with set-units before approving units-generation.")
    findings = record.get("findings", [])
    stage = PLAN_BY_ID[args.stage]
    review = record.get("review")
    if stage.get("reviewer") and (
        not review
        or review.get("attempt") != record["attempt"]
        or review.get("revision") != record["revision"]
    ):
        raise SystemExit(f"Record the declared reviewer verdict for the current revision of {args.stage}.")
    if args.decision == "approve" and findings:
        raise SystemExit("Outstanding findings require request-changes or override-and-approve.")
    if args.decision in {"request-changes", "override-and-approve"} and not (args.reason or "").strip():
        raise SystemExit(f"--reason is required for {args.decision}.")
    receipt = {"stage": args.stage, "unit": args.unit, "decision": args.decision, "reason": args.reason or "", "decidedAt": now(), "attempt": record["attempt"], "revision": record["revision"], "findings": findings}
    state["receipts"].append(receipt)
    if args.decision == "request-changes":
        record["status"] = "revising"; record["revision"] += 1; record["feedback"] = args.reason.strip()
        record.pop("review", None)
    else:
        record["status"] = "approved"; record.pop("feedback", None)
    if not current_work(state): state["status"] = "completed"
    save_state(root, state); audit(root, "GATE_DECIDED", **receipt)
    print(json.dumps({"decision": args.decision, "next": current_work(state)}, indent=2))


def cmd_validate(args: argparse.Namespace) -> None:
    project = Path(args.project).resolve(); root, state = load_state(project)
    errors: list[str] = []
    allowed_statuses = {"pending", "running", "awaiting_approval", "revising", "approved"}
    if state.get("schemaVersion") != 1: errors.append("schema version mismatch")
    if state.get("owner") != "collaborative-aidlc-kirocrew": errors.append("state owner mismatch")
    if state.get("stateVersion") != 7: errors.append("state version mismatch")
    if state.get("planVersion") != PLAN_VERSION: errors.append("plan version mismatch")
    digest = state.get("stateDigest")
    undigested = {key: value for key, value in state.items() if key != "stateDigest"}
    canonical = json.dumps(undigested, sort_keys=True, separators=(",", ":"))
    if digest != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        errors.append("state digest mismatch")

    normal_ids = [stage["id"] for stage in PLAN if not stage.get("for_each")]
    if set(state.get("stages", {})) != set(normal_ids):
        errors.append("non-unit stage set mismatch")
    for stage_id, record in state.get("stages", {}).items():
        if record.get("status") not in allowed_statuses:
            errors.append(f"{stage_id} has invalid status {record.get('status')}")
    for stage_id in INIT:
        if state.get("stages", {}).get(stage_id, {}).get("status") != "approved":
            errors.append(f"initialization stage {stage_id} is not approved")

    pre_ids = [stage["id"] for stage in PLAN[:11] if stage["id"] not in INIT]
    seen_incomplete = False
    for stage_id in pre_ids:
        status = state.get("stages", {}).get(stage_id, {}).get("status")
        if seen_incomplete and status != "pending":
            errors.append(f"pre-construction stage {stage_id} progressed out of order")
        if status != "approved":
            seen_incomplete = True

    units = state.get("units", {})
    for name, unit in units.items():
        if set(unit.get("stages", {})) != set(LANE_STAGE_IDS):
            errors.append(f"unit {name} stage set mismatch")
        for stage_id, record in unit.get("stages", {}).items():
            if record.get("status") not in allowed_statuses:
                errors.append(f"unit {name}/{stage_id} has invalid status {record.get('status')}")
        for dependency in unit.get("dependsOn", []):
            if dependency not in units or dependency == name:
                errors.append(f"{name} has invalid dependency {dependency}")

    if units:
        skeleton = state.get("walkingSkeleton")
        if skeleton not in units:
            errors.append("walking skeleton is not a registered unit")
        elif units[skeleton].get("dependsOn"):
            errors.append("walking skeleton has dependencies")
        for name, unit in units.items():
            seen_stage_incomplete = False
            progressed = False
            for stage_id in LANE_STAGE_IDS:
                status = unit.get("stages", {}).get(stage_id, {}).get("status")
                if status != "pending":
                    progressed = True
                if seen_stage_incomplete and status != "pending":
                    errors.append(f"unit {name}/{stage_id} progressed out of order")
                if status != "approved":
                    seen_stage_incomplete = True
            if progressed:
                for dependency in unit.get("dependsOn", []):
                    if dependency in units and not unit_complete(units[dependency]):
                        errors.append(f"unit {name} progressed before dependency {dependency} completed")
                if name != skeleton and skeleton in units and not unit_complete(units[skeleton]):
                    errors.append(f"unit {name} progressed before walking skeleton {skeleton} completed")
        remaining = set(units)
        batches: list[list[str]] = []
        while remaining:
            ready = sorted(
                name
                for name in remaining
                if all(dependency not in remaining for dependency in units[name].get("dependsOn", []))
            )
            if not ready:
                errors.append("unit dependency cycle detected")
                break
            batches.append(ready)
            remaining.difference_update(ready)
        if batches and batches != state.get("unitBatches"):
            errors.append("stored unit batches do not match dependency graph")
        if seen_incomplete and any(
            record.get("status") != "pending"
            for unit in units.values()
            for record in unit.get("stages", {}).values()
        ):
            errors.append("unit construction progressed before inception completed")

    lanes_complete = bool(units) and all(unit_complete(unit) for unit in units.values())
    post_ids = [stage["id"] for stage in PLAN[POST_LANE_START:]]
    seen_incomplete = False
    for stage_id in post_ids:
        status = state.get("stages", {}).get(stage_id, {}).get("status")
        if not lanes_complete and status != "pending":
            errors.append(f"post-lane stage {stage_id} progressed before units completed")
        if seen_incomplete and status != "pending":
            errors.append(f"post-lane stage {stage_id} progressed out of order")
        if status != "approved":
            seen_incomplete = True

    all_records = list(state.get("stages", {}).items()) + [
        (f"{unit_name}/{stage_id}", record)
        for unit_name, unit in units.items()
        for stage_id, record in unit.get("stages", {}).items()
    ]
    for identity, record in all_records:
        stage_id = identity.split("/")[-1]
        if PLAN_BY_ID.get(stage_id, {}).get("reviewer") and record.get("status") in {
            "awaiting_approval", "approved"
        }:
            review = record.get("review")
            if not review or review.get("attempt") != record.get("attempt") or review.get("revision") != record.get("revision"):
                errors.append(f"{identity} lacks a reviewer verdict for its current revision")

    for receipt in state.get("receipts", []):
        if receipt.get("decision") not in {"approve", "request-changes", "override-and-approve"}:
            errors.append("receipt has an invalid decision")
        if receipt.get("decision") in {"request-changes", "override-and-approve"} and not str(receipt.get("reason", "")).strip():
            errors.append("receipt requiring a reason has none")

    try:
        work = current_work(state)
        for item in work:
            if item["stage"] not in PLAN_BY_ID:
                errors.append(f"unknown current stage {item['stage']}")
    except (KeyError, StopIteration, TypeError) as error:
        work = []
        errors.append(f"current work cannot be resolved: {error}")
    if (not work) != (state.get("status") == "completed"):
        errors.append("workflow status disagrees with current work")

    result = {"valid": not errors, "errors": errors, "intentRoot": str(root), "current": work}
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(1)


def cmd_plan(args: argparse.Namespace) -> None:
    print(json.dumps({"version": PLAN_VERSION, "stages": PLAN}, indent=2))


def cmd_self_test(_: argparse.Namespace) -> None:
    units, batches = parse_unit_dag("""```yaml\nunits:\n  - name: api\n    depends_on: []\n  - name: web\n    depends_on: [api]\n```\n""")
    assert [u["name"] for u in units] == ["api", "web"] and batches == [["api"], ["web"]]
    with tempfile.TemporaryDirectory() as tmp:
        args = argparse.Namespace(project=tmp, space="collaborative-aidlc", title="Self test", intent="Build a test app", intent_file=None, project_type="greenfield")
        cmd_init(args)
        _, state = load_state(Path(tmp))
        assert current_work(state) == [{"stage": "reverse-engineering", "unit": None}]
    assert len(PLAN) == 25
    assert sum(1 for s in PLAN if s.get("reviewer")) == 10
    assert sum(1 for s in PLAN if s["id"] not in INIT) == 22
    print("workflow self-test: PASS")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--project", default=".")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("--title", required=True); init.add_argument("--intent"); init.add_argument("--intent-file"); init.add_argument("--project-type", choices=["greenfield","brownfield"], default="brownfield"); init.add_argument("--space", default="collaborative-aidlc"); init.set_defaults(func=cmd_init)
    status = sub.add_parser("status"); status.add_argument("--json", action="store_true"); status.set_defaults(func=cmd_status)
    context = sub.add_parser("context"); context.add_argument("--stage", required=True); context.add_argument("--unit"); context.set_defaults(func=cmd_context)
    start = sub.add_parser("start"); start.add_argument("--stage", required=True); start.add_argument("--unit"); start.set_defaults(func=cmd_start)
    finish = sub.add_parser("finish"); finish.add_argument("--stage", required=True); finish.add_argument("--unit"); finish.add_argument("--evidence"); finish.set_defaults(func=cmd_finish)
    requeue = sub.add_parser("requeue"); requeue.add_argument("--stage", required=True); requeue.add_argument("--unit"); requeue.add_argument("--reason", required=True); requeue.set_defaults(func=cmd_requeue)
    review = sub.add_parser("review"); review.add_argument("--stage", required=True); review.add_argument("--unit"); review.add_argument("--verdict", choices=["READY","NOT-READY","INCONCLUSIVE"], required=True); review.add_argument("--findings"); review.set_defaults(func=cmd_review)
    units = sub.add_parser("set-units"); units.add_argument("--artifact", required=True); units.add_argument("--walking-skeleton"); units.set_defaults(func=cmd_set_units)
    gate = sub.add_parser("gate"); gate.add_argument("--stage", required=True); gate.add_argument("--unit"); gate.add_argument("--decision", choices=["approve","request-changes","override-and-approve"], required=True); gate.add_argument("--reason"); gate.set_defaults(func=cmd_gate)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    sub.add_parser("self-test").set_defaults(func=cmd_self_test)
    return p


if __name__ == "__main__":
    parsed = parser().parse_args()
    parsed.func(parsed)
