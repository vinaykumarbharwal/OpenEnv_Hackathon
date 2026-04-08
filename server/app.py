"""Deployment entrypoint expected by OpenEnv validators."""

from openenv_bug_triage.app import app
from run import main as run_server


def main() -> None:
    """Run the local server entrypoint."""
    run_server()


if __name__ == "__main__":
    main()
