"""
Tests for the SubagentStart/SubagentStop tracking script.

Tests cover:
- SubagentStart creates/updates tracking file
- SubagentStop removes entries from tracking file
- Concurrent access safety
- Integration (start → verify → stop → verify)
"""
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest


def run_tracker(hooks_dir: Path, input_json: str) -> tuple:
    """Run the subagent_tracker.py script with given input.
    Returns (exit_code, stdout, stderr).
    """
    tracker_script = hooks_dir / "subagent_tracker.py"
    result = subprocess.run(
        [sys.executable, str(tracker_script)],
        input=input_json,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


def make_start_input(agent_id: str, agent_type: str, transcript_path: str) -> str:
    """Create SubagentStart hook input JSON."""
    return json.dumps({
        "hook_type": "SubagentStart",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "transcript_path": transcript_path,
    })


def make_stop_input(agent_id: str, transcript_path: str) -> str:
    """Create SubagentStop hook input JSON."""
    return json.dumps({
        "hook_type": "SubagentStop",
        "agent_id": agent_id,
        "transcript_path": transcript_path,
    })


def read_tracking_file(transcript_dir: Path) -> dict:
    """Read the agent tracking file."""
    tracking_file = transcript_dir / "subagents" / ".agent_types.json"
    if not tracking_file.exists():
        return {}
    return json.loads(tracking_file.read_text())


@pytest.fixture
def transcript_dir(tmp_path):
    """Create a temporary transcript directory."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.touch()
    return tmp_path


# ---------------------------------------------------------------------------
# TestSubagentTrackerStart
# ---------------------------------------------------------------------------

class TestSubagentTrackerStart:
    """Tests for SubagentStart event handling."""

    def test_start_creates_tracking_file(self, hooks_dir, transcript_dir):
        """SubagentStart creates tracking file with agent mapping."""
        transcript = str(transcript_dir / "transcript.jsonl")
        input_json = make_start_input("agent_abc", "Explore", transcript)
        code, stdout, stderr = run_tracker(hooks_dir, input_json)
        assert code == 0
        agent_map = read_tracking_file(transcript_dir)
        assert agent_map == {"agent_abc": "Explore"}

    def test_start_appends_to_existing(self, hooks_dir, transcript_dir):
        """SubagentStart appends to existing tracking file."""
        transcript = str(transcript_dir / "transcript.jsonl")

        # First agent
        input_json = make_start_input("agent_abc", "Explore", transcript)
        run_tracker(hooks_dir, input_json)

        # Second agent
        input_json = make_start_input("agent_def", "Plan", transcript)
        run_tracker(hooks_dir, input_json)

        agent_map = read_tracking_file(transcript_dir)
        assert agent_map == {"agent_abc": "Explore", "agent_def": "Plan"}

    def test_start_creates_subagents_directory(self, hooks_dir, transcript_dir):
        """SubagentStart creates subagents directory if needed."""
        transcript = str(transcript_dir / "transcript.jsonl")
        subagents_dir = transcript_dir / "subagents"
        assert not subagents_dir.exists()

        input_json = make_start_input("agent_abc", "Explore", transcript)
        run_tracker(hooks_dir, input_json)

        assert subagents_dir.exists()
        assert subagents_dir.is_dir()

    def test_start_missing_agent_id_exits_cleanly(self, hooks_dir, transcript_dir):
        """SubagentStart with missing agent_id exits cleanly (exit 0)."""
        transcript = str(transcript_dir / "transcript.jsonl")
        input_json = json.dumps({
            "hook_type": "SubagentStart",
            "agent_type": "Explore",
            "transcript_path": transcript,
        })
        code, stdout, stderr = run_tracker(hooks_dir, input_json)
        assert code == 0
        assert stdout == ""

    def test_start_missing_transcript_path_exits_cleanly(self, hooks_dir):
        """SubagentStart with missing transcript_path exits cleanly."""
        input_json = json.dumps({
            "hook_type": "SubagentStart",
            "agent_id": "agent_abc",
            "agent_type": "Explore",
        })
        code, stdout, stderr = run_tracker(hooks_dir, input_json)
        assert code == 0
        assert stdout == ""

    def test_start_empty_input_exits_cleanly(self, hooks_dir):
        """SubagentStart with empty input exits cleanly."""
        code, stdout, stderr = run_tracker(hooks_dir, "")
        assert code == 0
        assert stdout == ""

    def test_start_no_stdout_output(self, hooks_dir, transcript_dir):
        """SubagentStart never outputs to stdout (no blocking JSON)."""
        transcript = str(transcript_dir / "transcript.jsonl")
        input_json = make_start_input("agent_abc", "Explore", transcript)
        code, stdout, stderr = run_tracker(hooks_dir, input_json)
        assert stdout == ""


# ---------------------------------------------------------------------------
# TestSubagentTrackerStop
# ---------------------------------------------------------------------------

class TestSubagentTrackerStop:
    """Tests for SubagentStop event handling."""

    def test_stop_removes_agent(self, hooks_dir, transcript_dir):
        """SubagentStop removes agent from tracking file."""
        transcript = str(transcript_dir / "transcript.jsonl")

        # Start agent
        run_tracker(hooks_dir, make_start_input("agent_abc", "Explore", transcript))
        assert "agent_abc" in read_tracking_file(transcript_dir)

        # Stop agent
        code, stdout, stderr = run_tracker(hooks_dir, make_stop_input("agent_abc", transcript))
        assert code == 0
        assert "agent_abc" not in read_tracking_file(transcript_dir)

    def test_stop_nonexistent_agent_is_noop(self, hooks_dir, transcript_dir):
        """SubagentStop with non-existent agent_id is no-op."""
        transcript = str(transcript_dir / "transcript.jsonl")

        # Start one agent
        run_tracker(hooks_dir, make_start_input("agent_abc", "Explore", transcript))

        # Stop a different agent
        code, stdout, stderr = run_tracker(hooks_dir, make_stop_input("agent_xyz", transcript))
        assert code == 0
        # Original agent still present
        assert "agent_abc" in read_tracking_file(transcript_dir)

    def test_stop_missing_tracking_file_exits_cleanly(self, hooks_dir, transcript_dir):
        """SubagentStop with missing tracking file exits cleanly."""
        transcript = str(transcript_dir / "transcript.jsonl")
        code, stdout, stderr = run_tracker(hooks_dir, make_stop_input("agent_abc", transcript))
        assert code == 0
        assert stdout == ""

    def test_stop_no_stdout_output(self, hooks_dir, transcript_dir):
        """SubagentStop never outputs to stdout."""
        transcript = str(transcript_dir / "transcript.jsonl")
        run_tracker(hooks_dir, make_start_input("agent_abc", "Explore", transcript))
        code, stdout, stderr = run_tracker(hooks_dir, make_stop_input("agent_abc", transcript))
        assert stdout == ""


# ---------------------------------------------------------------------------
# TestSubagentTrackerConcurrency
# ---------------------------------------------------------------------------

class TestSubagentTrackerConcurrency:
    """Tests for concurrent access safety."""

    def test_two_simultaneous_starts(self, hooks_dir, transcript_dir):
        """Two simultaneous starts don't lose data (threading test)."""
        transcript = str(transcript_dir / "transcript.jsonl")
        results = {}

        def start_agent(agent_id, agent_type):
            input_json = make_start_input(agent_id, agent_type, transcript)
            code, _, _ = run_tracker(hooks_dir, input_json)
            results[agent_id] = code

        t1 = threading.Thread(target=start_agent, args=("agent_1", "Explore"))
        t2 = threading.Thread(target=start_agent, args=("agent_2", "Plan"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["agent_1"] == 0
        assert results["agent_2"] == 0

        agent_map = read_tracking_file(transcript_dir)
        assert "agent_1" in agent_map
        assert "agent_2" in agent_map

    def test_start_stop_interleaved(self, hooks_dir, transcript_dir):
        """Start + stop interleaved don't corrupt file."""
        transcript = str(transcript_dir / "transcript.jsonl")

        # Start agent 1
        run_tracker(hooks_dir, make_start_input("agent_1", "Explore", transcript))
        # Start agent 2
        run_tracker(hooks_dir, make_start_input("agent_2", "Plan", transcript))
        # Stop agent 1
        run_tracker(hooks_dir, make_stop_input("agent_1", transcript))

        agent_map = read_tracking_file(transcript_dir)
        assert "agent_1" not in agent_map
        assert agent_map.get("agent_2") == "Plan"

    def test_multiple_stops_same_agent(self, hooks_dir, transcript_dir):
        """Multiple stops for same agent_id don't error."""
        transcript = str(transcript_dir / "transcript.jsonl")
        run_tracker(hooks_dir, make_start_input("agent_abc", "Explore", transcript))

        # Stop multiple times
        for _ in range(3):
            code, stdout, stderr = run_tracker(hooks_dir, make_stop_input("agent_abc", transcript))
            assert code == 0
            assert stdout == ""


# ---------------------------------------------------------------------------
# TestSubagentTrackerIntegration
# ---------------------------------------------------------------------------

class TestSubagentTrackerIntegration:
    """Integration tests for the full start/stop lifecycle."""

    def test_start_stop_lifecycle(self, hooks_dir, transcript_dir):
        """Start → tracking file has entry → Stop → tracking file has no entry."""
        transcript = str(transcript_dir / "transcript.jsonl")

        # Start
        run_tracker(hooks_dir, make_start_input("agent_abc", "Explore", transcript))
        assert read_tracking_file(transcript_dir) == {"agent_abc": "Explore"}

        # Stop
        run_tracker(hooks_dir, make_stop_input("agent_abc", transcript))
        assert read_tracking_file(transcript_dir) == {}

    def test_multi_agent_lifecycle(self, hooks_dir, transcript_dir):
        """Start A → Start B → both present → Stop A → only B remains."""
        transcript = str(transcript_dir / "transcript.jsonl")

        run_tracker(hooks_dir, make_start_input("agent_a", "Explore", transcript))
        run_tracker(hooks_dir, make_start_input("agent_b", "Plan", transcript))

        agent_map = read_tracking_file(transcript_dir)
        assert agent_map == {"agent_a": "Explore", "agent_b": "Plan"}

        run_tracker(hooks_dir, make_stop_input("agent_a", transcript))
        agent_map = read_tracking_file(transcript_dir)
        assert agent_map == {"agent_b": "Plan"}
