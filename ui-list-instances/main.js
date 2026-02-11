const form = document.getElementById("form");
const compartmentInput = document.getElementById("compartmentId");
const resultDiv = document.getElementById("instances");

let rpcId = 1;

// Use the backend server directly (switch to your MCP server port for dev)
const MCP_BACKEND_URL = "http://localhost:3002/mcp";

async function callMcp({ method, params }) {
  const payload = {
    jsonrpc: "2.0",
    method,
    params,
    id: rpcId++
  };
  const resp = await fetch(MCP_BACKEND_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    // for local testing, include the following if you use credentials
    // credentials: "include"
  });
  const json = await resp.json();
  if (json.error) throw new Error(json.error.message);
  return json.result;
}

form.onsubmit = async (ev) => {
  ev.preventDefault();
  resultDiv.textContent = "Loading...";
  try {
    const result = await callMcp({
      method: "callTool",
      params: {
        toolName: "list_instances",
        arguments: { compartment_id: compartmentInput.value }
      }
    });
    renderInstances(result);
  } catch (e) {
    resultDiv.innerHTML = `<div class='error'>Error: ${e.message}</div>`;
  }
};

function renderInstances(result) {
  if (
    !result ||
    !result.structuredContent ||
    !Array.isArray(result.structuredContent.instances)
  ) {
    resultDiv.innerHTML = "<div class='error'>No instances or invalid response.</div>";
    return;
  }
  const instances = result.structuredContent.instances;
  if (!instances.length) {
    resultDiv.innerHTML = "<div>No instances found.</div>";
    return;
  }
  let html = `<table>
    <tr><th>Display Name</th><th>ID</th><th>State</th><th>Shape</th></tr>
    ${instances
      .map(
        (i) => `<tr>
        <td>${i.displayName}</td>
        <td style="font-size:80%">${i.id}</td>
        <td>${i.lifecycleState}</td>
        <td>${i.shape}</td>
      </tr>`
      )
      .join("")}
  </table>`;
  resultDiv.innerHTML = html;
}