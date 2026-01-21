"""Integration tests for the protect_directories.py hook."""

import subprocess
import sys
from pathlib import Path

# Get the hooks directory as absolute path
HOOKS_DIR = (Path(__file__).parent.parent / "hooks").resolve()
PROTECT_SCRIPT = HOOKS_DIR / "protect_directories.py"


def to_posix_path(path) -> str:
    """Convert path to forward slashes for JSON compatibility."""
    return str(path).replace("\\", "/")


def run_hook(input_json: str, cwd: str = None) -> tuple[str, int]:
    """Run the hook with given JSON input and return (output, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(PROTECT_SCRIPT)],
        input=input_json,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.stdout + result.stderr, result.returncode


class TestHookIntegration:
    """Test the protect_directories.py hook directly."""

    def test_blocks_when_block_file_exists(self, tmp_path):
        """Hook should block when .block file exists in directory."""
        (tmp_path / ".block").write_text("{}")
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block decision, got: {output}"

    def test_allows_when_no_block_file(self, tmp_path):
        """Hook should allow (no output) when no .block file exists."""
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, exit_code = run_hook(input_json, cwd=str(tmp_path))

        assert exit_code == 0, f"Expected exit 0, got {exit_code}"
        assert "block" not in output.lower(), f"Expected allow (no block), got: {output}"

    def test_detects_block_in_parent_directory(self, tmp_path):
        """Hook should detect .block file in parent directory."""
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)
        (parent / ".block").write_text("{}")
        file_path = to_posix_path(child / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(child))

        assert "block" in output.lower(), f"Expected block from parent .block, got: {output}"

    def test_detects_block_local_file(self, tmp_path):
        """Hook should detect .block.local file."""
        (tmp_path / ".block.local").write_text("{}")
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block decision, got: {output}"

    def test_allowed_pattern_permits_matching_file(self, tmp_path):
        """Hook should allow files matching allowed patterns."""
        (tmp_path / ".block").write_text('{"allowed": ["*.txt"]}')
        file_path = to_posix_path(tmp_path / "test.txt")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" not in output.lower(), f"Expected allow for *.txt pattern, got: {output}"

    def test_allowed_pattern_blocks_non_matching_file(self, tmp_path):
        """Hook should block files not matching allowed patterns."""
        (tmp_path / ".block").write_text('{"allowed": ["*.txt"]}')
        file_path = to_posix_path(tmp_path / "test.js")

        input_json = f'{{"tool_name": "Edit", "tool_input": {{"file_path": "{file_path}"}}}}'
        output, _ = run_hook(input_json, cwd=str(tmp_path))

        assert "block" in output.lower(), f"Expected block for non-matching file, got: {output}"
