"""Tests for the `feather init` command."""

from __future__ import annotations

from pathlib import Path


class TestInit:
    def test_scaffolds_project(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        result = runner.invoke(app, ["init", str(tmp_path / "test-project")])
        assert result.exit_code == 0
        project = tmp_path / "test-project"
        assert (project / "feather.yaml").exists()
        assert (project / "pyproject.toml").exists()
        assert (project / ".gitignore").exists()
        assert (project / ".env.example").exists()

    def test_init_nonempty_dir_fails(self, runner, tmp_path: Path):
        from feather_etl.cli import app

        project = tmp_path / "existing"
        project.mkdir()
        (project / "somefile.txt").write_text("exists")
        result = runner.invoke(app, ["init", str(project)])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_init_allows_git_only_dir(self, runner, tmp_path: Path):
        """UX-3: .git directory should not block feather init."""
        from feather_etl.cli import app

        project = tmp_path / "git-project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / ".gitignore").write_text("*.duckdb\n")
        result = runner.invoke(app, ["init", str(project)])
        assert result.exit_code == 0
        assert (project / "feather.yaml").exists()

    def test_init_dot_uses_cwd_name(self, runner, tmp_path: Path):
        """UX-2: feather init . should use directory name, not empty string."""
        import os

        from feather_etl.cli import app

        project = tmp_path / "my-client"
        project.mkdir()
        original_cwd = os.getcwd()
        try:
            os.chdir(project)
            result = runner.invoke(app, ["init", "."])
            assert result.exit_code == 0
            toml = (project / "pyproject.toml").read_text()
            assert 'name = ""' not in toml
            assert "my-client" in toml
        finally:
            os.chdir(original_cwd)
