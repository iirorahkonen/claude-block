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


def run_hook(hooks_dir: Path, input_json: str) -> Tuple[int, str, str]:
    """
    Run the protect_directories.py hook with given input.
    Returns (exit_code, stdout, stderr).
    """
    hook_script = hooks_dir / "protect_directories.py"
    result = subprocess.run(
        [sys.executable, str(hook_script)],
        input=input_json,
        capture_output=True,
        text=True
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
