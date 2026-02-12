"""
MCP HTTP Server using fastmcp and FastAPI (with CORS)
- Registers tools with @mcp.tool, resource UI with @mcp.resource.
- Built for direct uvicorn execution: add CORS middleware for browser support.
"""

import json
import logging
from mcp.server.fastmcp import FastMCP
import oci
import os
import uvicorn
import sys
from starlette.middleware.cors import CORSMiddleware

mcp = FastMCP(name="python-mcp-http-server", stateless_http=True)
resourceUri = "ui://python-mcp-http-server/resources/ui-list-instances.html"
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3001"))

@mcp.tool(
    description="List OCI Compute Instances",
    meta={
        "ui": {
            "resourceUri": resourceUri
        },
        "ui/resourceUri": resourceUri
    }
)
def list_instances(compartment_id: str) -> dict:
    config_file = os.getenv("OCI_CONFIG_FILE", oci.config.DEFAULT_LOCATION)
    profile_name = os.getenv("OCI_CONFIG_PROFILE", oci.config.DEFAULT_PROFILE)
    config = oci.config.from_file(
        file_location=config_file,
        profile_name=profile_name
    )
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
    return { "items": items }


@mcp.resource(
    uri=resourceUri,
    mime_type="text/html;profile=mcp-app",
    meta={"ui": {"csp": {"resourceDomains": ["https://esm.sh", "https://unpkg.com"]}}},
)
def list_instances_ui() -> str:
    resource_path = os.path.join(os.path.dirname(__file__), "resources", "ui-list-instances.html")
    with open(resource_path, "r", encoding="utf-8") as f:
        html = f.read()
    return html


def create_app():
    """Create the ASGI app (for uvicorn reload mode)."""
    # Pass host=HOST to disable DNS rebinding protection for non-localhost deployments
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if "--stdio" in sys.argv:
        # Claude Desktop mode
        mcp.run(transport="stdio")
    elif "--reload" in sys.argv:
        # Reload mode - pass app as string so uvicorn can reimport
        print(f"Say Server listening on http://{HOST}:{PORT}/mcp (reload mode)")
        uvicorn.run("server:create_app", host=HOST, port=PORT, reload=True, factory=True)
    else:
        # HTTP mode
        app = create_app()
        print(f"Say Server listening on http://{HOST}:{PORT}/mcp")
        uvicorn.run(app, host=HOST, port=PORT)