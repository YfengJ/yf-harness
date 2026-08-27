from __future__ import annotations

import json
import os
import sys


def reply(request: dict[str, object], result: dict[str, object]) -> None:
    print(
        json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}),
        flush=True,
    )


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method == "initialize":
        reply(
            request,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            },
        )
    elif method == "tools/list":
        reply(
            request,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo a value",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                        "annotations": {"readOnlyHint": True},
                    },
                    {
                        "name": "hidden",
                        "description": "Filtered tool",
                        "inputSchema": {"type": "object"},
                    },
                ]
            },
        )
    elif method == "tools/call":
        params = request.get("params", {})
        arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
        value = arguments.get("value", "") if isinstance(arguments, dict) else ""
        reply(
            request,
            {
                "content": [
                    {
                        "type": "text",
                        "text": f"{value}|allowed={os.environ.get('MCP_ALLOWED', '')}"
                        f"|secret={os.environ.get('MCP_SECRET', '')}",
                    }
                ],
                "structuredContent": {"echo": value},
                "isError": False,
            },
        )
