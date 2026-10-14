#!/usr/bin/env python3
"""Validate the portable Collaborative AI-DLC KiroCrew adapter."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "collaborative-aidlc-kirocrew" / "scripts" / "workflow.py"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_runner():
    spec = importlib.util.spec_from_file_location("collaborative_aidlc_runner", RUNNER)
    if not spec or not spec.loader:
        fail("cannot load Collaborative AI-DLC runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    manifest = json.loads((ROOT / "app.json").read_text(encoding="utf-8"))
    if manifest.get("name") != "collaborative-aidlc-kirocrew":
        fail("unexpected app name")
    if manifest.get("minKiroCrewVersion") != "0.8.0":
        fail("adapter must target the exercised stable KiroCrew 0.8 contract")
    forbidden = {"ui", "backend", "mcpServers", "crons"}
    if forbidden.intersection(manifest):
        fail("adapter must not add a custom UI, backend process, MCP server, or cron")
    if manifest.get("skills") != ["skills/collaborative-aidlc-kirocrew"]:
        fail("skill must use the globally unique app namespace")
    mixed_crews = ROOT / "skills" / "collaborative-aidlc-kirocrew" / "references" / "mixed-crews.md"
    if not mixed_crews.is_file():
        fail("mixed coding-agent crews guide is missing")
    for relative in [*manifest.get("agents", []), *manifest.get("skills", [])]:
        if not (ROOT / relative).exists():
            fail(f"manifest path does not exist: {relative}")

    runner = load_runner()
    plan = runner.PLAN
    if len(plan) != 25:
        fail(f"expected 25 stages, found {len(plan)}")
    if len({stage['id'] for stage in plan}) != len(plan):
        fail("stage ids are not unique")
    if sum(1 for stage in plan if stage['id'] not in runner.INIT) != 22:
        fail("expected 22 human-gated stages")
    if sum(1 for stage in plan if stage.get("reviewer")) != 10:
        fail("expected 10 reviewer stages")
    if [stage['id'] for stage in plan if stage.get("for_each")] != runner.LANE_STAGE_IDS:
        fail("per-unit stage projection drifted")

    agent_names = set()
    for relative in manifest["agents"]:
        data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        if data.get("name") in agent_names:
            fail(f"duplicate agent name: {data.get('name')}")
        agent_names.add(data.get("name"))
        unknown = set(data) - {
            "name", "description", "model", "prompt", "tools", "allowedTools",
            "excludedTools", "resources", "permissions", "mcpServers",
        }
        if unknown:
            fail(f"unsupported portable agent fields in {relative}: {sorted(unknown)}")
        invalid_tools = set(data.get("tools", [])) - {
            "fs_read", "fs_write", "execute_bash", "grep", "glob", "@kirocrew-core",
        }
        if invalid_tools:
            fail(f"non-canonical KiroCrew tools in {relative}: {sorted(invalid_tools)}")

    referenced = {
        runner.RUNTIME_AGENTS[agent]
        for stage in plan
        for agent in [stage["lead"], *stage.get("support", []), stage.get("reviewer")]
        if agent and agent != "orchestrator"
    }
    missing = referenced - agent_names
    if missing:
        fail(f"missing referenced agents: {sorted(missing)}")
    if any(not name.startswith("collaborative-aidlc-") for name in agent_names):
        fail("every installed agent must use the collaborative-aidlc namespace")

    subprocess.run([sys.executable, str(RUNNER), "self-test"], check=True)
    print(f"adapter validation: PASS ({len(plan)} stages, {len(agent_names)} agents)")


if __name__ == "__main__":
    main()
