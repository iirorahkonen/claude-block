"""
Tests for child directory .block file detection.

When a command targets a parent directory (e.g., rm -rf parent/),
the hook should scan descendant directories for .block files and
block the operation if any are found. This prevents bypassing
directory-level protections by operating on a parent directory.
"""
from tests.conftest import (
    create_block_file,
    create_local_block_file,
    get_block_reason,
    is_blocked,
    make_bash_input,
    run_hook,
)


class TestChildDirBlockDetection:
    """Tests that parent directory operations check child directories for .block files."""

    def test_rm_rf_parent_blocked_by_child_block_file(self, test_dir, hooks_dir):
        """rm -rf on parent should be blocked when child has .block file."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), f"Expected block due to child .block, got: {stdout}"

    def test_rm_rf_parent_blocked_by_deeply_nested_block_file(self, test_dir, hooks_dir):
        """rm -rf on parent should be blocked when deeply nested child has .block file."""
        parent_dir = test_dir / "parent"
        deep_dir = parent_dir / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        create_block_file(deep_dir)

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), f"Expected block due to deeply nested .block, got: {stdout}"

    def test_rm_rf_parent_allowed_when_no_child_block_files(self, test_dir, hooks_dir):
        """rm -rf on parent should be allowed when no child has .block file."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        # No .block files anywhere

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert exit_code == 0
        assert not is_blocked(stdout)

    def test_rm_rf_parent_blocked_by_child_block_local_file(self, test_dir, hooks_dir):
        """rm -rf on parent should be blocked when child has .block.local file."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_local_block_file(child_dir)

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), f"Expected block due to child .block.local, got: {stdout}"

    def test_rm_parent_without_rf_blocked_by_child_block(self, test_dir, hooks_dir):
        """rm on parent directory should be blocked when child has .block file."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input(f"rm -r {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), f"Expected block due to child .block, got: {stdout}"

    def test_rmdir_blocked_by_descendant_block_file(self, test_dir, hooks_dir):
        """rmdir on parent should be blocked when descendant has .block file."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input(f"rmdir {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), f"Expected block due to descendant .block, got: {stdout}"


class TestChildDirBlockWithRelativePaths:
    """Tests that relative path operations also check child directories."""

    def test_rm_rf_relative_path_blocked_by_child_block(self, test_dir, hooks_dir):
        """rm -rf with relative path should be blocked when child has .block file."""
        parent_dir = test_dir / "myproject"
        child_dir = parent_dir / "protected"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        # Use relative path; cwd is test_dir
        input_json = make_bash_input("rm -rf myproject")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json, cwd=test_dir)

        assert is_blocked(stdout), f"Expected block for relative path with child .block, got: {stdout}"

    def test_rm_rf_relative_dot_slash_blocked_by_child_block(self, test_dir, hooks_dir):
        """rm -rf ./ should be blocked when child directory has .block file."""
        child_dir = test_dir / "protected_child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input("rm -rf ./")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json, cwd=test_dir)

        assert is_blocked(stdout), f"Expected block for ./ with child .block, got: {stdout}"

    def test_rm_rf_relative_subdir_blocked_by_grandchild_block(self, test_dir, hooks_dir):
        """rm -rf subdir/ should be blocked when grandchild has .block file."""
        subdir = test_dir / "subdir"
        grandchild = subdir / "level1" / "level2"
        grandchild.mkdir(parents=True)
        create_block_file(grandchild)

        input_json = make_bash_input("rm -rf subdir")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json, cwd=test_dir)

        assert is_blocked(stdout), f"Expected block for grandchild .block, got: {stdout}"


class TestChildDirBlockEdgeCases:
    """Tests for edge cases in child directory block detection."""

    def test_rm_rf_with_trailing_slash_blocked_by_child_block(self, test_dir, hooks_dir):
        """rm -rf parent/ (trailing slash) should be blocked by child .block."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input(f"rm -rf {parent_dir}/")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            f"Expected block for trailing slash path. Got: {stdout}"
        )

    def test_rm_rf_dot_blocked_by_child_block(self, test_dir, hooks_dir):
        """rm -rf . should be blocked when child directory has .block file."""
        child_dir = test_dir / "protected_child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input("rm -rf .")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json, cwd=test_dir)

        assert is_blocked(stdout), (
            f"Expected block for '.' with child .block. Got: {stdout}"
        )

    def test_rm_file_inside_parent_does_not_trigger_descendant_check(
        self, test_dir, hooks_dir
    ):
        """rm on a file inside parent should not be blocked by sibling child .block."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        # Target is a file, not a directory — descendant check should not apply
        target_file = parent_dir / "somefile.txt"
        target_file.write_text("content")
        input_json = make_bash_input(f"rm {target_file}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert not is_blocked(stdout), (
            f"rm on a file should not be blocked by sibling .block. Got: {stdout}"
        )

    def test_chained_rm_rf_blocked_by_child_block(self, test_dir, hooks_dir):
        """rm -rf in chained command should be blocked by child .block."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)

        input_json = make_bash_input(f"rm -rf {parent_dir} && echo done")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            f"Expected block for chained command. Got: {stdout}"
        )

    def test_rm_rf_blocks_when_block_in_target_dir_itself(self, test_dir, hooks_dir):
        """rm -rf dir should be blocked when .block is in the target dir itself.

        This catches the case where test_directory_protected misses the .block
        because dirname('dir') goes to the parent, skipping dir/.block.
        The descendant check finds it via os.walk.
        """
        target_dir = test_dir / "target"
        target_dir.mkdir(parents=True)
        create_block_file(target_dir)

        input_json = make_bash_input(f"rm -rf {target_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            f"Expected block when .block is in target dir itself. Got: {stdout}"
        )


class TestChildDirBlockWithGuides:
    """Tests that guide messages from child .block files are shown."""

    def test_child_block_guide_message_is_shown(self, test_dir, hooks_dir):
        """Guide from child .block file should be shown when parent dir is targeted."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir, '{"guide": "This directory contains protected data."}')

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        reason = get_block_reason(stdout)
        assert "This directory contains protected data." in reason

    def test_child_local_guide_used_when_both_markers_exist(self, test_dir, hooks_dir):
        """When child has both .block and .block.local, local guide takes precedence."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir, '{"guide": "Main guide"}')
        create_local_block_file(child_dir, '{"guide": "Local guide"}')

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        reason = get_block_reason(stdout)
        assert "Local guide" in reason, (
            f"Expected local guide to take precedence. Got: {reason}"
        )

    def test_target_dir_local_guide_used_when_both_markers_exist(self, test_dir, hooks_dir):
        """When target dir has both .block and .block.local, local guide takes precedence."""
        target_dir = test_dir / "target"
        target_dir.mkdir(parents=True)
        create_block_file(target_dir, '{"guide": "Main guide"}')
        create_local_block_file(target_dir, '{"guide": "Local guide"}')

        input_json = make_bash_input(f"rm -rf {target_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)
        reason = get_block_reason(stdout)
        assert "Local guide" in reason, (
            f"Expected local guide to take precedence. Got: {reason}"
        )

    def test_child_block_with_patterns_still_blocks_parent_rm(self, test_dir, hooks_dir):
        """Child .block with specific patterns should still block parent rm -rf."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir, '{"blocked": ["*.secret"]}')

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            "rm -rf on parent should be blocked when child has any .block file, "
            f"regardless of child's patterns. Got: {stdout}"
        )

    def test_child_block_with_allowed_patterns_still_blocks_parent_rm(self, test_dir, hooks_dir):
        """Child .block with allowed patterns should still block parent rm -rf."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir, '{"allowed": ["*.txt"]}')

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            "rm -rf on parent should be blocked when child has any .block file. "
            f"Got: {stdout}"
        )


class TestChildDirBlockWithParentProtection:
    """Tests interaction between parent and child directory protections."""

    def test_parent_already_blocked_doesnt_need_child_check(self, test_dir, hooks_dir):
        """When parent is already blocked, child check is redundant but shouldn't cause issues."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(parent_dir)  # Parent has .block
        create_block_file(child_dir)   # Child also has .block

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout)

    def test_block_in_one_of_multiple_children(self, test_dir, hooks_dir):
        """Should block if any one child has .block even if siblings don't."""
        parent_dir = test_dir / "parent"
        child_a = parent_dir / "child_a"
        child_b = parent_dir / "child_b"
        child_c = parent_dir / "child_c"
        child_a.mkdir(parents=True)
        child_b.mkdir(parents=True)
        child_c.mkdir(parents=True)
        # Only child_b has .block
        create_block_file(child_b)

        input_json = make_bash_input(f"rm -rf {parent_dir}")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            f"Should block when any child has .block. Got: {stdout}"
        )

    def test_mv_parent_dir_blocked_by_child_block(self, test_dir, hooks_dir):
        """mv on parent directory should be blocked when child has .block file."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)
        dest_dir = test_dir / "dest"
        dest_dir.mkdir(parents=True)

        input_json = make_bash_input(f"mv {parent_dir} {dest_dir}/renamed")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        assert is_blocked(stdout), (
            f"mv on parent dir with protected child should be blocked. Got: {stdout}"
        )

    def test_cp_parent_dir_blocked_by_child_block(self, test_dir, hooks_dir):
        """cp from parent directory should still be blocked since cp extracts the path too."""
        parent_dir = test_dir / "parent"
        child_dir = parent_dir / "child"
        child_dir.mkdir(parents=True)
        create_block_file(child_dir)
        dest_dir = test_dir / "dest"
        dest_dir.mkdir(parents=True)

        input_json = make_bash_input(f"cp -r {parent_dir} {dest_dir}/copy")
        exit_code, stdout, stderr = run_hook(hooks_dir, input_json)

        # cp extracts both source and dest as paths; source dir has protected child
        assert is_blocked(stdout), (
            f"cp on parent dir with protected child should be blocked. Got: {stdout}"
        )
