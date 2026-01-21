"""
Bash command detection tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    is_blocked,
    make_bash_input,
    run_hook,
)


class TestBashCommands:
    """Tests for bash command path detection."""

    def test_detects_rm_command_target(self, test_dir, hooks_dir):
        """Should detect rm command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"rm {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_rm_rf_command_target(self, test_dir, hooks_dir):
        """Should detect rm -rf command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"rm -rf {project_dir}/dir")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_touch_command_target(self, test_dir, hooks_dir):
        """Should detect touch command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"touch {project_dir}/newfile.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_mv_command_targets(self, test_dir, hooks_dir):
        """Should detect mv command targets."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        other_dir = test_dir / "other"
        other_dir.mkdir(parents=True)
        input_json = make_bash_input(f"mv {other_dir}/file.txt {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_cp_command_targets(self, test_dir, hooks_dir):
        """Should detect cp command targets."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        other_dir = test_dir / "other"
        other_dir.mkdir(parents=True)
        input_json = make_bash_input(f"cp {other_dir}/file.txt {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_output_redirection_target(self, test_dir, hooks_dir):
        """Should detect output redirection target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"echo 'hello' > {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_tee_command_target(self, test_dir, hooks_dir):
        """Should detect tee command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"echo 'hello' | tee {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_tee_a_append_command_target(self, test_dir, hooks_dir):
        """Should detect tee -a append command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"echo 'hello' | tee -a {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_mkdir_command_target(self, test_dir, hooks_dir):
        """Should detect mkdir command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"mkdir -p {project_dir}/newdir")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_allows_read_only_bash_commands(self, test_dir, hooks_dir):
        """Should allow read-only bash commands."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"cat {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_allows_ls_command_in_protected_directory(self, test_dir, hooks_dir):
        """Should allow ls command in protected directory."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"ls -la {project_dir}/")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_detects_rmdir_command_target(self, test_dir, hooks_dir):
        """Should detect rmdir command target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        empty_dir = project_dir / "emptydir"
        empty_dir.mkdir(parents=True)
        input_json = make_bash_input(f"rmdir {empty_dir}")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_append_redirection_target(self, test_dir, hooks_dir):
        """Should detect append redirection target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"echo 'hello' >> {project_dir}/file.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_detects_dd_command_with_of_target(self, test_dir, hooks_dir):
        """Should detect dd command with of= target."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"dd if=/dev/zero of={project_dir}/file.bin bs=1 count=1")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_bash_command_with_multiple_protected_paths_blocks_first_match(self, test_dir, hooks_dir):
        """Should block if any path in a bash command is protected."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        other_dir = test_dir / "other"
        other_dir.mkdir(parents=True)
        input_json = make_bash_input(f"cp {other_dir}/safe.txt {project_dir}/protected.txt")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)


class TestBashCommandsQuotedPaths:
    """Tests for bash commands with quoted paths containing spaces."""

    def test_touch_with_double_quoted_path(self, test_dir, hooks_dir):
        """Should detect touch command with double-quoted path containing spaces."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f'touch "{project_dir}/my file.txt"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_touch_with_single_quoted_path(self, test_dir, hooks_dir):
        """Should detect touch command with single-quoted path containing spaces."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f"touch '{project_dir}/my file.txt'")

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_rm_with_quoted_path_containing_spaces(self, test_dir, hooks_dir):
        """Should detect rm command with quoted path containing spaces."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f'rm "{project_dir}/my important file.txt"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_mkdir_with_quoted_path(self, test_dir, hooks_dir):
        """Should detect mkdir command with quoted path."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f'mkdir -p "{project_dir}/new dir/sub dir"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_mv_with_both_paths_quoted(self, test_dir, hooks_dir):
        """Should detect mv command with both source and destination quoted."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        other_dir = test_dir / "other"
        other_dir.mkdir(parents=True)
        input_json = make_bash_input(f'mv "{other_dir}/source file.txt" "{project_dir}/dest file.txt"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_cp_with_quoted_paths(self, test_dir, hooks_dir):
        """Should detect cp command with quoted paths."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        other_dir = test_dir / "other"
        other_dir.mkdir(parents=True)
        input_json = make_bash_input(f'cp "{other_dir}/source.txt" "{project_dir}/my dest.txt"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_redirect_to_quoted_path(self, test_dir, hooks_dir):
        """Should detect output redirection to quoted path."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f'echo "hello" > "{project_dir}/my output.txt"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_tee_with_quoted_path(self, test_dir, hooks_dir):
        """Should detect tee command with quoted path."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)
        input_json = make_bash_input(f'echo "hello" | tee "{project_dir}/my output.txt"')

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
