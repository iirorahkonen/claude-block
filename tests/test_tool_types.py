"""
Tool type tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_write_input,
    make_notebook_input,
    run_hook,
    is_blocked,
)


class TestToolTypes:
    """Tests for different tool types."""

    def test_write_tool_is_blocked_in_protected_directory(self, test_dir, hooks_dir):
        """Write tool should be blocked in protected directory."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_write_input(str(project_dir / "new-file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_notebookedit_tool_is_blocked_in_protected_directory(self, test_dir, hooks_dir):
        """NotebookEdit tool should be blocked in protected directory."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_notebook_input(str(project_dir / "notebook.ipynb"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_unknown_tools_are_allowed(self, test_dir, hooks_dir):
        """Unknown tools should be allowed."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        import json
        input_json = json.dumps({
            "tool_name": "UnknownTool",
            "tool_input": {"path": str(project_dir / "file.txt")}
        })

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)
