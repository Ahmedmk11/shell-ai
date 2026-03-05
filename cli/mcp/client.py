from langchain_mcp_adapters.client import MultiServerMCPClient

async def instantiate_client():
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",
                "command": "sys.executable",
                "args": ["cli/mcp/servers/github/server.py"]
            },
        }
    )

    tools = await client.get_tools()

    return client, tools
