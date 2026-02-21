"""
Shared fixtures and utilities for block plugin tests.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import pytest


@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary test directory."""
    return tmp_path


@pytest.fixture
def hooks_dir():
    """Path to the hooks directory."""
    return Path(__file__).parent.parent / "hooks"


# Utility functions - can be imported by test modules
def create_block_file(directory: Path, content: Optional[str] = None) -> Path:
    """Create a .block file with given content."""
    directory.mkdir(parents=True, exist_ok=True)
    block_file = directory / ".block"
    if content:
        block_file.write_text(content)
    else:
        block_file.touch()
    return block_file


def create_local_block_file(directory: Path, content: Optional[str] = None) -> Path:
    """Create a .block.local file with given content."""
    directory.mkdir(parents=True, exist_ok=True)
    block_file = directory / ".block.local"
    if content:
        block_file.write_text(content)
    else:
        block_file.touch()
    return block_file


def make_edit_input(file_path: str) -> str:
    """Create hook input JSON for Edit tool."""
    return json.dumps({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "old",
            "new_string": "new"
        }
    })


def make_write_input(file_path: str) -> str:
    """Create hook input JSON for Write tool."""
    return json.dumps({
        "tool_name": "Write",
        "tool_input": {
            "file_path": file_path,
            "content": "test content"
        }
    })


def make_bash_input(command: str) -> str:
    """Create hook input JSON for Bash tool."""
    return json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": command
        }
    })


def make_notebook_input(notebook_path: str) -> str:
    """Create hook input JSON for NotebookEdit tool."""
    return json.dumps({
        "tool_name": "NotebookEdit",
        "tool_input": {
            "notebook_path": notebook_path,
            "cell_number": 0,
            "new_source": "# test"
        }
    })


def _add_agent_fields(base_json: str, tool_use_id: str, transcript_path: str) -> str:
    """Inject agent context fields into a base hook input JSON string."""
    data = json.loads(base_json)
    if tool_use_id:
        data["tool_use_id"] = tool_use_id
    if transcript_path:
        data["transcript_path"] = transcript_path
    return json.dumps(data)


def make_edit_input_with_agent(file_path: str, tool_use_id: str = "", transcript_path: str = "") -> str:
    """Create hook input JSON for Edit tool with agent context fields."""
    return _add_agent_fields(make_edit_input(file_path), tool_use_id, transcript_path)


def make_write_input_with_agent(file_path: str, tool_use_id: str = "", transcript_path: str = "") -> str:
    """Create hook input JSON for Write tool with agent context fields."""
    return _add_agent_fields(make_write_input(file_path), tool_use_id, transcript_path)


def make_bash_input_with_agent(command: str, tool_use_id: str = "", transcript_path: str = "") -> str:
    """Create hook input JSON for Bash tool with agent context fields."""
    return _add_agent_fields(make_bash_input(command), tool_use_id, transcript_path)


def create_agent_tracking_file(transcript_dir: Path, agent_map: dict) -> Path:
    """Create the subagent tracking file with given agent map."""
    subagents_dir = transcript_dir / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    tracking_file = subagents_dir / ".agent_types.json"
    tracking_file.write_text(json.dumps(agent_map))
    return tracking_file


def create_agent_transcript(transcript_dir: Path, agent_id: str, tool_use_ids: list) -> Path:
    """Create a mock subagent transcript file containing the given tool_use_ids."""
    subagents_dir = transcript_dir / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = subagents_dir / f"{agent_id}.jsonl"
    lines = []
    for tuid in tool_use_ids:
        lines.append(json.dumps({"tool_use_id": tuid, "type": "tool_use"}))
    transcript_file.write_text("\n".join(lines))
    return transcript_file


def run_hook(hooks_dir: Path, input_json: str, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """
    Run the protect_directories.py hook with given input.
    Returns (exit_code, stdout, stderr).

    Args:
        hooks_dir: Path to the hooks directory
        input_json: JSON input to pass to the hook via stdin
        cwd: Optional working directory to run the hook from
    """
    hook_script = hooks_dir / "protect_directories.py"
    result = subprocess.run(
        [sys.executable, str(hook_script)],
        input=input_json,
        capture_output=True,
        text=True,
        cwd=cwd
    )
    return result.returncode, result.stdout, result.stderr


def is_blocked(output: str) -> bool:
    """Check if hook output indicates blocking."""
    return '"decision"' in output and '"block"' in output


def get_block_reason(output: str) -> str:
    """Extract the block reason from hook output."""
    try:
        data = json.loads(output)
        return data.get("reason", "")
    except json.JSONDecodeError:
        return ""
