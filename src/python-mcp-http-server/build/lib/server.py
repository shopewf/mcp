"""
Minimal MCP HTTP Server in Python (FastAPI)
- Exposes POST /mcp endpoint, speaks MCP/JSON-RPC protocol
- Register additional tools by editing the TOOL_HANDLERS dict
- MCP tools take arguments (dict) and return an MCP ToolResult dict
- Handles "callTool" requests; can be extended as needed
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Print middleware to log all incoming requests
@app.middleware("http")
async def log_all_requests(request, call_next):
    import sys
    print(f"[MIDDLEWARE] {request.method} {request.url} headers: {dict(request.headers)}", flush=True)
    response = await call_next(request)
    return response


# Tool handlers registry: tool_name -> handler(arguments: dict) -> ToolResult dict
TOOL_HANDLERS = {}

# Example tool: echo
def tool_echo(arguments):
    msg = arguments.get("message", "")
    return {
        "content": [{"type": "text", "text": msg}],
        "structuredContent": {"message": msg}
    }
TOOL_HANDLERS["echo"] = tool_echo

# List OCI compute instances (requires OCI SDK config)
def tool_list_instances(arguments):
    import oci, os
    compartment_id = arguments.get("compartment_id")
    if not compartment_id:
        return {
            "content": [{"type": "text", "text": "[ERROR: Missing compartment_id]"}],
            "structuredContent": {}
        }

    # Custom auth logic (SecurityTokenSigner path)
    config_file = os.getenv("OCI_CONFIG_FILE", oci.config.DEFAULT_LOCATION)
    profile_name = os.getenv("OCI_CONFIG_PROFILE", oci.config.DEFAULT_PROFILE)
    config = oci.config.from_file(
        file_location=config_file,
        profile_name=profile_name
    )
    # Optionally add custom UA
    config["additional_user_agent"] = "mcp-http-server/1.0.0"

    private_key = oci.signer.load_private_key_from_file(config.get("key_file"))
    token_file = os.path.expanduser(config.get("security_token_file"))
    with open(token_file, "r") as f:
        token = f.read()
    signer = oci.auth.signers.SecurityTokenSigner(token, private_key)

    compute = oci.core.ComputeClient(config, signer=signer)
    result = oci.pagination.list_call_get_all_results(
        compute.list_instances, compartment_id=compartment_id
    ).data
    items = [
        {
            "id": i.id,
            "displayName": i.display_name,
            "lifecycleState": str(i.lifecycle_state),
            "shape": i.shape
        } for i in result
    ]
    return {
        "content": [{"type": "json", "json": items}],
        "structuredContent": {"instances": items}
    }


TOOL_HANDLERS["list_instances"] = tool_list_instances
@app.post("/mcp")
async def mcp_entry(request: Request):
    req = await request.json()
    print(f"[mcp_entry] RAW REQUEST: {req}", flush=True)
    # Minimal JSON-RPC/MCP parsing
    rpc_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})
    if method != "callTool":
        print(f"[mcp_entry] Received unknown method: {method} -- params: {params}")
        # Temporary: Return a dummy manifest for "getManifest" for protocol handshake
        if method == "getManifest":
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "name": "python-mcp-http-server",
                        "tools": [
                            {"name": "list_instances", "description": "List OCI Compute Instances"}
                        ]
                    }
                }
            )
        # You could add more handlers here for e.g. "describeServer" if required
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
        )
    tool_name = params.get("toolName")
    arguments = params.get("arguments", {})
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
            }
        )
    try:
        result = handler(arguments)
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": rpc_id, "result": result}
        )
    except Exception as ex:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32000, "message": f"Internal error: {ex}"}
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3002)