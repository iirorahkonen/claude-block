"""
Marker file protection tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    create_local_block_file,
    make_edit_input,
    make_bash_input,
    make_write_input,
    run_hook,
    is_blocked,
)


class TestMarkerFileProtection:
    """Tests for .block and .block.local file protection."""

    def test_blocks_modification_of_block_file(self, test_dir, hooks_dir):
        """Should block modification of .block file."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*"]}')  # Even with allow all pattern
        input_json = make_edit_input(str(project_dir / ".block"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "Cannot modify" in stdout

    def test_blocks_modification_of_block_local_file(self, test_dir, hooks_dir):
        """Should block modification of .block.local file."""
        project_dir = test_dir / "project"
        create_local_block_file(project_dir, '{}')
        input_json = make_edit_input(str(project_dir / ".block.local"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "Cannot modify" in stdout

    def test_blocks_rm_command_targeting_block_file(self, test_dir, hooks_dir):
        """Should block rm command targeting .block file."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"rm {project_dir}/.block")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "Cannot modify" in stdout

    def test_allows_creating_new_block_file(self, test_dir, hooks_dir):
        """Should allow creating a new .block file."""
        project_dir = test_dir / "project"
        project_dir.mkdir(parents=True)
        input_json = make_write_input(str(project_dir / ".block"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_allows_creating_new_block_local_file(self, test_dir, hooks_dir):
        """Should allow creating a new .block.local file."""
        project_dir = test_dir / "project"
        project_dir.mkdir(parents=True)
        input_json = make_write_input(str(project_dir / ".block.local"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)
