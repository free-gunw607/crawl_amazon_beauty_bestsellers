from __future__ import annotations

import fcntl
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts" / "run_locked_schedule.sh"


def test_locked_schedule_preserves_child_exit_status(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(WRAPPER), str(tmp_path / "lock"), "bash", "-c", "exit 7"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 7


def test_locked_schedule_reports_overlap_as_success(tmp_path: Path) -> None:
    lock_path = tmp_path / "lock"
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            ["bash", str(WRAPPER), str(lock_path), "true"],
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0
    assert "overlapping invocation" in result.stdout
