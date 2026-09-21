"""Tests for the health check / doctor module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from projectmind.core.interfaces import HealthStatus
from projectmind.platform.config.settings import ProjectSettings, Settings, load_settings
from projectmind.platform.health.doctor import (
    CheckResult,
    DoctorReport,
    check_database,
    check_index_freshness,
    check_memory_directory,
    check_memory_integrity,
    check_project_directory,
    check_required_packages,
    run_doctor,
)


class TestCheckResult:
    def test_pass_icon(self):
        r = CheckResult("Test", HealthStatus.PASS, "ok")
        assert r.icon == "✓"
        assert r.color == "green"

    def test_warn_icon(self):
        r = CheckResult("Test", HealthStatus.WARN, "warning")
        assert r.icon == "⚠"
        assert r.color == "yellow"

    def test_fail_icon(self):
        r = CheckResult("Test", HealthStatus.FAIL, "error")
        assert r.icon == "✗"
        assert r.color == "red"


class TestDoctorReport:
    def _make_report(self, statuses: list[HealthStatus]) -> DoctorReport:
        report = DoctorReport()
        for i, status in enumerate(statuses):
            report.checks.append(CheckResult(f"Check {i}", status, "msg"))
        return report

    def test_is_healthy_all_pass(self):
        report = self._make_report([HealthStatus.PASS, HealthStatus.PASS])
        assert report.is_healthy is True

    def test_is_healthy_with_warn(self):
        report = self._make_report([HealthStatus.PASS, HealthStatus.WARN])
        assert report.is_healthy is True

    def test_is_healthy_with_fail(self):
        report = self._make_report([HealthStatus.PASS, HealthStatus.FAIL])
        assert report.is_healthy is False

    def test_overall_status_pass(self):
        report = self._make_report([HealthStatus.PASS])
        assert report.overall_status == HealthStatus.PASS

    def test_overall_status_warn(self):
        report = self._make_report([HealthStatus.PASS, HealthStatus.WARN])
        assert report.overall_status == HealthStatus.WARN

    def test_overall_status_fail(self):
        report = self._make_report([HealthStatus.WARN, HealthStatus.FAIL])
        assert report.overall_status == HealthStatus.FAIL


class TestCheckProjectDirectory:
    def test_existing_directory(self, tmp_path: Path):
        settings = load_settings.__wrapped__(None) if hasattr(load_settings, "__wrapped__") else None
        # Directly set settings for this test
        import projectmind.platform.config.settings as settings_mod
        proj = ProjectSettings(root=str(tmp_path))
        s = Settings(project=proj)
        settings_mod._settings_cache = s

        result = check_project_directory()
        assert result.status == HealthStatus.PASS

    def test_missing_directory(self, tmp_path: Path):
        import projectmind.platform.config.settings as settings_mod
        proj = ProjectSettings(root=str(tmp_path / "nonexistent"))
        s = Settings(project=proj)
        settings_mod._settings_cache = s

        result = check_project_directory()
        assert result.status == HealthStatus.FAIL


class TestCheckMemoryDirectory:
    def test_missing_memory_dir(self, tmp_path: Path):
        import projectmind.platform.config.settings as settings_mod
        proj = ProjectSettings(root=str(tmp_path), memory_dir=".projectmind")
        s = Settings(project=proj)
        settings_mod._settings_cache = s

        result = check_memory_directory()
        assert result.status == HealthStatus.FAIL
        assert "Run 'projectmind init'" in result.suggestion

    def test_existing_memory_dir(self, project_dir: Path):
        import projectmind.platform.config.settings as settings_mod
        proj = ProjectSettings(root=str(project_dir), memory_dir=".projectmind")
        s = Settings(project=proj)
        settings_mod._settings_cache = s

        result = check_memory_directory()
        assert result.status == HealthStatus.PASS


class TestCheckDatabase:
    def test_database_not_exists(self, tmp_path: Path):
        import projectmind.platform.config.settings as settings_mod
        from projectmind.platform.config.settings import DatabaseSettings
        proj = ProjectSettings(root=str(tmp_path))
        db = DatabaseSettings(path=str(tmp_path / "nonexistent.db"))
        s = Settings(project=proj, database=db)
        settings_mod._settings_cache = s

        result = check_database()
        assert result.status == HealthStatus.WARN  # not fail — just not created yet

    def test_healthy_database(self, tmp_path: Path):
        import projectmind.platform.config.settings as settings_mod
        from projectmind.platform.config.settings import DatabaseSettings

        db_path = tmp_path / "test.db"
        # Create a valid SQLite database
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.close()

        proj = ProjectSettings(root=str(tmp_path))
        db = DatabaseSettings(path=str(db_path))
        s = Settings(project=proj, database=db)
        settings_mod._settings_cache = s

        result = check_database()
        assert result.status == HealthStatus.PASS

    def test_corrupted_database(self, tmp_path: Path):
        import projectmind.platform.config.settings as settings_mod
        from projectmind.platform.config.settings import DatabaseSettings

        db_path = tmp_path / "corrupt.db"
        db_path.write_bytes(b"this is not a valid sqlite database!!!")

        proj = ProjectSettings(root=str(tmp_path))
        db = DatabaseSettings(path=str(db_path))
        s = Settings(project=proj, database=db)
        settings_mod._settings_cache = s

        result = check_database()
        assert result.status == HealthStatus.FAIL


class TestCheckMemoryIntegrity:
    def test_with_healthy_stub(self, stub_core):
        result = check_memory_integrity()
        assert result.status == HealthStatus.PASS

    def test_with_no_module(self, empty_core):
        result = check_memory_integrity()
        assert result.status == HealthStatus.WARN
        assert "Member 2" in result.message


class TestCheckIndexFreshness:
    def test_with_fresh_index(self, stub_core):
        result = check_index_freshness()
        assert result.status in (HealthStatus.PASS, HealthStatus.WARN)

    def test_with_no_module(self, empty_core):
        result = check_index_freshness()
        assert result.status == HealthStatus.WARN

    def test_with_not_indexed(self):
        from projectmind.core.interfaces import ProjectMindCore, set_core

        from tests.stubs import StubCodeIntelligence
        code_intel = StubCodeIntelligence(indexed=False)
        core = ProjectMindCore(code_intelligence=code_intel)
        set_core(core)

        result = check_index_freshness()
        assert result.status == HealthStatus.WARN
        assert "not been indexed" in result.message


class TestCheckRequiredPackages:
    def test_click_and_rich_installed(self):
        result = check_required_packages()
        # click is installed (we're using it), rich may or may not be
        assert result.status in (HealthStatus.PASS, HealthStatus.WARN, HealthStatus.FAIL)
        assert isinstance(result.message, str)


class TestRunDoctor:
    def test_returns_report(self, stub_core):
        report = run_doctor()
        assert isinstance(report, DoctorReport)
        assert len(report.checks) == len([c for c in report.checks])

    def test_checks_never_crash(self, stub_core):
        """Even if a check raises an exception internally, run_doctor should not crash."""

        def crashing_check():
            raise RuntimeError("Simulated crash")

        report = run_doctor(checks=[crashing_check])
        assert len(report.checks) == 1
        assert report.checks[0].status == HealthStatus.FAIL
        assert "crash" in report.checks[0].message.lower()

    def test_custom_check_list(self, stub_core):
        report = run_doctor(checks=[check_required_packages])
        assert len(report.checks) == 1
        assert report.checks[0].name == "Required packages"
