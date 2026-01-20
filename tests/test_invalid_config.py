"""
Invalid configuration tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestInvalidConfig:
    """Tests for invalid configuration handling."""

    def test_blocks_with_error_when_both_allowed_and_blocked_specified(self, test_dir, hooks_dir):
        """Should block with error when both allowed and blocked are specified."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt"], "blocked": ["*.js"]}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "cannot specify both allowed and blocked" in stdout

    def test_treats_invalid_json_as_block_all(self, test_dir, hooks_dir):
        """Invalid JSON should be treated as block all."""
        project_dir = test_dir / "project"
        project_dir.mkdir(parents=True)
        (project_dir / ".block").write_text("this is not json")
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
