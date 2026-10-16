"""Redis queue worker for deployment jobs.

Usage:
  uv run python -m devdeploy_api.worker
"""

from __future__ import annotations

from devdeploy_api.pipeline import worker_loop


def main() -> None:
    print("DevDeploy worker listening on Redis list devdeploy:deployments", flush=True)
    worker_loop(once=False, step_delay=0.2)


if __name__ == "__main__":
    main()
