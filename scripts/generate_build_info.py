from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sha = subprocess.run(
        ["git", "rev-parse", "--short=5", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    timestamp = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    payload = {"build_sha": sha, "build_timestamp": timestamp}
    (project_root / "build-info.json").write_text(
        json.dumps(payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Build info: {sha} {timestamp}")


if __name__ == "__main__":
    main()
