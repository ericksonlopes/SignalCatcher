"""One-time desktop OAuth consent; tokens stay in the user's credential directory."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.services.oauth_credentials import write_oauth_credentials


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize the server to copy videos to My Drive.")
    parser.add_argument(
        "--client-json",
        type=Path,
        required=True,
        help="Desktop OAuth client JSON downloaded from Google Cloud.",
    )
    parser.add_argument(
        "--token",
        type=Path,
        required=True,
        help="Private destination for the authorized_user token JSON.",
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with args.client_json.open(encoding="utf-8") as source:
        client = json.load(source)
    if "installed" not in client:
        parser.error("Use a Desktop OAuth client JSON, not a service-account private key.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(client, ["https://www.googleapis.com/auth/drive"])
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=args.port,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )
    if not credentials.refresh_token:
        raise RuntimeError("Google did not provide offline access. Repeat the consent flow.")
    write_oauth_credentials(args.token, json.loads(credentials.to_json()))
    print(f"Authorization saved to {args.token.resolve()}. Do not commit or share this file.")


if __name__ == "__main__":
    main()
