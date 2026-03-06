import sys

from langchain_mcp_adapters.client import MultiServerMCPClient

async def instantiate_client():
    client = MultiServerMCPClient(
        {
            "github": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["cli/mcp/servers/github_server.py"]
            },
        }
    )

    tools = await client.get_tools()

    return client, tools
