from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "collaborative-aidlc-kirocrew" / "scripts" / "workflow.py"
SPEC = importlib.util.spec_from_file_location("workflow", RUNNER)
assert SPEC and SPEC.loader
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class CollaborativeAidlcTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        workflow.cmd_init(
            argparse.Namespace(
                project=str(self.project),
                space="collaborative-aidlc",
                title="Test intent",
                intent="Build a small service",
                intent_file=None,
                project_type="greenfield",
            )
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def args(self, **values):
        return argparse.Namespace(project=str(self.project), unit=None, **values)

    def _write_outputs(self, root: Path, stage: dict, unit: str | None = None) -> None:
        output_dir = workflow.artifact_dir(root, stage, unit)
        output_dir.mkdir(parents=True, exist_ok=True)
        for output in workflow.required_outputs(stage):
            body = f"# {output}\n\n## Evidence\nRepository evidence.\n\n## Result\nResult.\n"
            if output == "unit-of-work-dependency":
                body = (
                    "# Unit dependencies\n\n## Units\n\n"
                    "```yaml\nunits:\n  - name: foundation\n    depends_on: []\n"
                    "  - name: feature\n    depends_on: [foundation]\n```\n\n"
                    "## Rationale\nFoundation precedes feature.\n"
                )
            (output_dir / f"{output}.md").write_text(body, encoding="utf-8")

    def test_initial_state_and_digest_are_valid(self) -> None:
        root, state = workflow.load_state(self.project)
        self.assertEqual(workflow.current_work(state), [{"stage": "reverse-engineering", "unit": None}])
        workflow.cmd_validate(argparse.Namespace(project=str(self.project)))
        self.assertTrue((root / "aidlc-state.md").exists())

    def test_out_of_order_start_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            workflow.cmd_start(self.args(stage="requirements-analysis"))

    def test_context_paths_are_project_relative_for_remote_handoffs(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            workflow.cmd_context(self.args(stage="reverse-engineering"))
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["projectRoot"], ".")
        self.assertFalse(Path(payload["intentRoot"]).is_absolute())
        self.assertFalse(Path(payload["artifactDirectory"]).is_absolute())
        self.assertTrue(
            all(not Path(path).is_absolute() for path in payload["requiredArtifactFiles"])
        )

    def test_running_remote_assignment_can_be_requeued(self) -> None:
        workflow.cmd_start(self.args(stage="reverse-engineering"))
        with self.assertRaises(SystemExit):
            workflow.cmd_requeue(self.args(stage="reverse-engineering", reason=""))
        workflow.cmd_requeue(
            self.args(stage="reverse-engineering", reason="Remote crew became unavailable")
        )
        _, state = workflow.load_state(self.project)
        record = state["stages"]["reverse-engineering"]
        self.assertEqual(record["status"], "revising")
        self.assertEqual(record["revision"], 1)
        workflow.cmd_start(self.args(stage="reverse-engineering"))
        _, state = workflow.load_state(self.project)
        self.assertEqual(state["stages"]["reverse-engineering"]["attempt"], 2)

    def test_stage_output_check_and_gate_advance(self) -> None:
        stage_id = "reverse-engineering"
        workflow.cmd_start(self.args(stage=stage_id))
        root, _ = workflow.load_state(self.project)
        stage = workflow.PLAN_BY_ID[stage_id]
        output_dir = workflow.artifact_dir(root, stage, None)
        output_dir.mkdir(parents=True, exist_ok=True)
        for output in workflow.required_outputs(stage):
            (output_dir / f"{output}.md").write_text(
                f"# {output}\n\n## Evidence\nRepository evidence.\n\n## Result\nResult.\n",
                encoding="utf-8",
            )
        workflow.cmd_finish(self.args(stage=stage_id, evidence="unit test"))
        workflow.cmd_gate(self.args(stage=stage_id, decision="approve", reason=None))
        _, state = workflow.load_state(self.project)
        self.assertEqual(workflow.current_work(state), [{"stage": "practices-discovery", "unit": None}])

    def test_findings_require_recorded_override_reason(self) -> None:
        stage_id = "reverse-engineering"
        workflow.cmd_start(self.args(stage=stage_id))
        workflow.cmd_finish(self.args(stage=stage_id, evidence=None))
        with self.assertRaises(SystemExit):
            workflow.cmd_gate(self.args(stage=stage_id, decision="approve", reason=None))
        with self.assertRaises(SystemExit):
            workflow.cmd_gate(self.args(stage=stage_id, decision="request-changes", reason=None))
        with self.assertRaises(SystemExit):
            workflow.cmd_gate(self.args(stage=stage_id, decision="override-and-approve", reason=None))
        workflow.cmd_gate(
            self.args(stage=stage_id, decision="override-and-approve", reason="Facilitator accepts the missing exercise artifacts")
        )
        _, state = workflow.load_state(self.project)
        self.assertEqual(state["receipts"][-1]["decision"], "override-and-approve")

    def test_declared_reviewer_must_be_recorded(self) -> None:
        root, state = workflow.load_state(self.project)
        state["stages"]["reverse-engineering"]["status"] = "approved"
        state["stages"]["practices-discovery"]["status"] = "approved"
        state["stages"]["requirements-analysis"]["status"] = "awaiting_approval"
        workflow.save_state(root, state)
        args = self.args(stage="requirements-analysis", decision="approve", reason=None)
        with self.assertRaises(SystemExit):
            workflow.cmd_gate(args)
        workflow.cmd_review(
            self.args(stage="requirements-analysis", verdict="READY", findings="No findings")
        )
        workflow.cmd_gate(args)

    def test_unit_dag_is_batched_and_cycles_are_refused(self) -> None:
        units, batches = workflow.parse_unit_dag(
            "```yaml\nunits:\n  - name: api\n    depends_on: []\n  - name: ui\n    depends_on: [api]\n```\n"
        )
        self.assertEqual([unit["name"] for unit in units], ["api", "ui"])
        self.assertEqual(batches, [["api"], ["ui"]])
        with self.assertRaises(ValueError):
            workflow.parse_unit_dag(
                "```yaml\nunits:\n  - name: api\n    depends_on: [ui]\n  - name: ui\n    depends_on: [api]\n```\n"
            )

    def test_walking_skeleton_must_be_a_root_unit(self) -> None:
        root, state = workflow.load_state(self.project)
        state["stages"]["units-generation"]["status"] = "awaiting_approval"
        workflow.save_state(root, state)
        artifact = self.project / "units.md"
        artifact.write_text(
            "```yaml\nunits:\n  - name: foundation\n    depends_on: []\n  - name: feature\n    depends_on: [foundation]\n```\n",
            encoding="utf-8",
        )
        with self.assertRaises(SystemExit):
            workflow.cmd_set_units(
                argparse.Namespace(
                    project=str(self.project),
                    artifact=str(artifact),
                    walking_skeleton="feature",
                )
            )

    def test_reviewer_must_run_again_after_request_changes(self) -> None:
        root, state = workflow.load_state(self.project)
        state["stages"]["reverse-engineering"]["status"] = "approved"
        state["stages"]["practices-discovery"]["status"] = "approved"
        record = state["stages"]["requirements-analysis"]
        record.update({"status": "awaiting_approval", "attempt": 1})
        workflow.save_state(root, state)
        workflow.cmd_review(
            self.args(stage="requirements-analysis", verdict="READY", findings="No findings")
        )
        workflow.cmd_gate(
            self.args(
                stage="requirements-analysis",
                decision="request-changes",
                reason="Clarify the acceptance criteria",
            )
        )
        workflow.cmd_start(self.args(stage="requirements-analysis"))
        workflow.cmd_finish(self.args(stage="requirements-analysis", evidence="rerun"))
        with self.assertRaises(SystemExit):
            workflow.cmd_gate(
                self.args(
                    stage="requirements-analysis",
                    decision="override-and-approve",
                    reason="Accept current draft",
                )
            )

    def test_per_unit_inputs_exclude_sibling_units(self) -> None:
        root, state = workflow.load_state(self.project)
        state["units"] = {
            "api": {"dependsOn": [], "stages": {}},
            "ui": {"dependsOn": [], "stages": {}},
        }
        for unit in ("api", "ui"):
            path = root / "construction" / unit / "functional-design" / "business-logic-model.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Model\n", encoding="utf-8")
        found = workflow.find_inputs(
            root, workflow.PLAN_BY_ID["nfr-requirements"], "api", state
        )
        self.assertEqual(
            found["business-logic-model"],
            ["construction/api/functional-design/business-logic-model.md"],
        )

    def test_empty_intent_leaves_no_partial_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                workflow.cmd_init(
                    argparse.Namespace(
                        project=tmp,
                        space="collaborative-aidlc",
                        title="Empty",
                        intent="",
                        intent_file=None,
                        project_type="greenfield",
                    )
                )
            self.assertFalse((Path(tmp) / "aidlc").exists())

    def test_digest_valid_out_of_order_state_is_rejected(self) -> None:
        root, state = workflow.load_state(self.project)
        state["stages"]["feedback-optimization"]["status"] = "approved"
        workflow.save_state(root, state)
        with self.assertRaises(SystemExit):
            workflow.cmd_validate(argparse.Namespace(project=str(self.project)))

    def test_dependency_unit_cannot_run_before_walking_skeleton(self) -> None:
        root, state = workflow.load_state(self.project)
        for stage in workflow.PLAN[:11]:
            state["stages"][stage["id"]]["status"] = "approved"
        blank_stages = lambda: {
            stage_id: {"status": "pending", "attempt": 0, "revision": 0}
            for stage_id in workflow.LANE_STAGE_IDS
        }
        state["units"] = {
            "foundation": {"name": "foundation", "dependsOn": [], "stages": blank_stages()},
            "feature": {
                "name": "feature",
                "dependsOn": ["foundation"],
                "stages": blank_stages(),
            },
        }
        state["units"]["feature"]["stages"]["functional-design"]["status"] = "running"
        state["unitBatches"] = [["foundation"], ["feature"]]
        state["walkingSkeleton"] = "foundation"
        workflow.save_state(root, state)
        with self.assertRaises(SystemExit):
            workflow.cmd_validate(argparse.Namespace(project=str(self.project)))

    def test_pointer_publication_failure_rolls_back_new_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = workflow.atomic_text

            def fail_active_space(path: Path, value: str) -> None:
                if path.name == "active-space":
                    raise OSError("simulated pointer failure")
                original(path, value)

            workflow.atomic_text = fail_active_space
            try:
                with self.assertRaises(OSError):
                    workflow.cmd_init(
                        argparse.Namespace(
                            project=tmp,
                            space="collaborative-aidlc",
                            title="Pointer failure",
                            intent="Build a service",
                            intent_file=None,
                            project_type="greenfield",
                        )
                    )
            finally:
                workflow.atomic_text = original
            project = Path(tmp)
            self.assertFalse((project / "aidlc" / "active-space").exists())
            self.assertFalse(
                (project / "aidlc" / "spaces" / "collaborative-aidlc" / "intents" / "active-intent").exists()
            )
            self.assertEqual(
                list((project / "aidlc" / "spaces" / "collaborative-aidlc" / "intents").glob("*-pointer-failure")),
                [],
            )

    def test_complete_workflow_progression(self) -> None:
        while True:
            root, state = workflow.load_state(self.project)
            work = workflow.current_work(state)
            if not work:
                break
            for item in work:
                stage_id = item["stage"]
                unit = item.get("unit")
                stage = workflow.PLAN_BY_ID[stage_id]
                args = argparse.Namespace(project=str(self.project), stage=stage_id, unit=unit)
                workflow.cmd_start(args)
                self._write_outputs(root, stage, unit)
                workflow.cmd_finish(
                    argparse.Namespace(
                        project=str(self.project),
                        stage=stage_id,
                        unit=unit,
                        evidence="full progression test",
                    )
                )
                if stage_id == "units-generation":
                    workflow.cmd_set_units(
                        argparse.Namespace(
                            project=str(self.project),
                            artifact=str(
                                workflow.artifact_dir(root, stage, None)
                                / "unit-of-work-dependency.md"
                            ),
                            walking_skeleton="foundation",
                        )
                    )
                if stage.get("reviewer"):
                    workflow.cmd_review(
                        argparse.Namespace(
                            project=str(self.project),
                            stage=stage_id,
                            unit=unit,
                            verdict="READY",
                            findings="No findings",
                        )
                    )
                workflow.cmd_gate(
                    argparse.Namespace(
                        project=str(self.project),
                        stage=stage_id,
                        unit=unit,
                        decision="approve",
                        reason=None,
                    )
                )
        _, final_state = workflow.load_state(self.project)
        self.assertEqual(final_state["status"], "completed")
        workflow.cmd_validate(argparse.Namespace(project=str(self.project)))


if __name__ == "__main__":
    unittest.main()
