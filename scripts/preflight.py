from app.config import get_settings


def main() -> None:
    settings = get_settings()
    credentials = settings.google_oauth_credentials.resolve()
    token = settings.google_calendar_mcp_token_path.resolve()

    if not credentials.is_file():
        raise SystemExit(
            f"Google OAuth credentials file not found: {credentials}"
        )

    if not token.is_file() or token.stat().st_size == 0:
        raise SystemExit(
            "Google Calendar token is missing or empty. "
            "Run the MCP authentication flow first."
        )

    print("Google Calendar credentials: ready")


if __name__ == "__main__":
    main()

