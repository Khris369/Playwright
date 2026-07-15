from __future__ import annotations

import argparse

from app.services.workflow_artifacts import cleanup_artifacts_older_than


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete old workflow run artifacts.")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Retention window in days. Defaults to WORKFLOW_ARTIFACT_RETENTION_DAYS.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Maximum artifact rows to clean in one run.",
    )
    args = parser.parse_args()
    result = cleanup_artifacts_older_than(days=args.days, batch_size=args.batch_size)
    print(result)


if __name__ == "__main__":
    main()
