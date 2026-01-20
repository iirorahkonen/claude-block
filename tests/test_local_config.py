"""
Local configuration file tests for the block plugin.
"""
from tests.conftest import (
    create_block_file,
    create_local_block_file,
    make_edit_input,
    run_hook,
    is_blocked,
)


class TestLocalConfig:
    """Tests for .block.local configuration files."""

    def test_local_file_alone_blocks_operations(self, test_dir, hooks_dir):
        """Local file alone should block operations."""
        project_dir = test_dir / "project"
        create_local_block_file(project_dir)
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_local_file_extends_main_blocked_patterns(self, test_dir, hooks_dir):
        """Local file should extend main blocked patterns."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["*.lock"]}')
        create_local_block_file(project_dir, '{"blocked": ["*.test.ts"]}')

        # Both patterns should be blocked
        input_json = make_edit_input(str(project_dir / "yarn.lock"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        input_json = make_edit_input(str(project_dir / "app.test.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Non-blocked file should be allowed
        input_json = make_edit_input(str(project_dir / "app.ts"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_local_guide_overrides_main_guide(self, test_dir, hooks_dir):
        """Local guide should override main guide."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"guide": "Main guide"}')
        create_local_block_file(project_dir, '{"guide": "Local guide"}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "Local guide" in stdout
        assert "Main guide" not in stdout

    def test_merged_blocked_patterns_from_main_and_local(self, test_dir, hooks_dir):
        """Blocked patterns should be merged from both files."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"blocked": ["*.lock"]}')
        create_local_block_file(project_dir, '{"blocked": ["*.secret"]}')

        # Both patterns should be blocked
        input_json = make_edit_input(str(project_dir / "package.lock"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        input_json = make_edit_input(str(project_dir / "api.secret"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # Non-blocked file should be allowed
        input_json = make_edit_input(str(project_dir / "config.json"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_cannot_mix_allowed_and_blocked_between_main_and_local(self, test_dir, hooks_dir):
        """Cannot mix allowed and blocked modes between main and local."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt"]}')
        create_local_block_file(project_dir, '{"blocked": ["*.secret"]}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "cannot mix allowed and blocked" in stdout

    def test_local_allowed_list_overrides_main_allowed_list(self, test_dir, hooks_dir):
        """Local allowed list should override main allowed list."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt", "*.md"]}')
        create_local_block_file(project_dir, '{"allowed": ["*.js"]}')

        # .txt was allowed in main but not in local - should be blocked
        input_json = make_edit_input(str(project_dir / "file.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        # .js is allowed in local - should be allowed
        input_json = make_edit_input(str(project_dir / "file.js"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert exit_code == 0

    def test_both_configs_empty_uses_local_guide(self, test_dir, hooks_dir):
        """When both configs are empty, local guide should be used."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"guide": "Main guide message"}')
        create_local_block_file(project_dir, '{"guide": "Local guide message"}')
        input_json = make_edit_input(str(project_dir / "file.txt"))

        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        assert "Local guide message" in stdout
        assert "Main guide message" not in stdout

    def test_main_empty_with_local_blocked_patterns_blocks_all(self, test_dir, hooks_dir):
        """When main is empty and local has blocked patterns, all operations are blocked."""
        project_dir = test_dir / "project"
        create_block_file(project_dir)  # Empty = block all
        create_local_block_file(project_dir, '{"blocked": ["*.secret"]}')

        # All files blocked (empty main is most restrictive)
        input_json = make_edit_input(str(project_dir / "file.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

        input_json = make_edit_input(str(project_dir / "file.secret"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)

    def test_main_with_allowed_patterns_local_empty_blocks_all(self, test_dir, hooks_dir):
        """When main has allowed patterns but local is empty, all operations are blocked."""
        project_dir = test_dir / "project"
        create_block_file(project_dir, '{"allowed": ["*.txt"]}')
        create_local_block_file(project_dir)  # Empty = block all

        # Even allowed patterns from main are overridden by local empty
        input_json = make_edit_input(str(project_dir / "file.txt"))
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)
        assert is_blocked(stdout)
