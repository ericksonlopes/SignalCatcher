import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.database.connector import Session
from src.core.database.job_control import JobControlRepository


def main() -> None:
    with Session.begin() as session:
        JobControlRepository(session).request("youtube_process_errors")
    print("Retry request queued; the worker respects backoff and attempt limits.")


if __name__ == "__main__":
    main()
