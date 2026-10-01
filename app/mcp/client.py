from langchain_mcp_adapters.client import MultiServerMCPClient
from app.config import Settings
from app.mcp.tools import CALENDAR_TOOLS

def create_mcp_client(settings: Settings) -> MultiServerMCPClient:
    client = MultiServerMCPClient (
    {
    "calendar": {
        "transport": "stdio",
        "command": r"C:\Program Files\nodejs\npx.cmd",
        "args": ["--yes", "@cocal/google-calendar-mcp@2.6.3","start"],
        "env" : {
            "GOOGLE_OAUTH_CREDENTIALS" : str(settings.google_oauth_credentials.resolve()) ,
            "GOOGLE_CALENDAR_MCP_TOKEN_PATH" : str(settings.google_calendar_mcp_token_path.resolve()),
            "ENABLED_TOOLS" : ",".join(CALENDAR_TOOLS),
    }
    }
    }
    )
    return client

