"""Small helpers for the Fabric and Power BI REST APIs, signed in through the Azure CLI (az login)."""

import base64
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

FABRIC = "https://api.fabric.microsoft.com/v1"   # items: create/update/list semantic models and reports
PBI = "https://api.powerbi.com/v1.0/myorg"       # datasets: refresh, DAX queries
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
PBI_RESOURCE = "https://analysis.windows.net/powerbi/api"

_tokens = {}


def token(resource):
    """Get an access token for the signed-in az account (cached per API)."""
    if resource not in _tokens:
        result = subprocess.run(
            # On Windows az is az.cmd, which subprocess can't find from plain "az" (Linux has no az.cmd)
            [shutil.which("az.cmd") or "az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
            check=True, capture_output=True, text=True)
        _tokens[resource] = result.stdout.strip()
    return _tokens[resource]


def call(method, url, body=None, skill="semantic-model-authoring"):
    """Send a request; return (status, headers, json body or None). Raises on HTTP errors."""
    resource = PBI_RESOURCE if url.startswith(PBI) else FABRIC_RESOURCE
    headers = {"Authorization": f"Bearer {token(resource)}"}
    if url.startswith(FABRIC):
        headers["x-ms-fabric-skill"] = skill
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
            return response.status, dict(response.headers), (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"{method} {url} -> {err.code}: {err.read().decode('utf-8', 'replace')}") from None


def wait_for_operation(headers, label, skill="semantic-model-authoring"):
    """Fabric returns 202 + an operation URL for slow requests; poll it until it finishes."""
    url = headers.get("Location") or f"{FABRIC}/operations/{headers['x-ms-operation-id']}"
    while True:
        time.sleep(min(max(int(headers.get("Retry-After", 5)), 2), 20))
        _, headers, body = call("GET", url, skill=skill)
        state = (body or {}).get("status")
        print(f"  {label}: {state}")
        if state == "Succeeded":
            try:
                return call("GET", url.rstrip("/") + "/result", skill=skill)[2]
            except RuntimeError:
                return None
        if state in ("Failed", "Undefined"):
            raise RuntimeError(f"{label} failed: {json.dumps(body, indent=2)}")


def my_workspace_id(skill="semantic-model-authoring"):
    """ID of the signed-in user's personal workspace ('My workspace')."""
    _, _, body = call("GET", f"{FABRIC}/workspaces", skill=skill)
    for workspace in body["value"]:
        if workspace.get("type") == "Personal":
            return workspace["id"]
    raise RuntimeError("My workspace not found")


def find_items(workspace_id, item_type, name, skill="semantic-model-authoring"):
    _, _, body = call("GET", f"{FABRIC}/workspaces/{workspace_id}/items?type={item_type}", skill=skill)
    return [item for item in body.get("value", []) if item["displayName"] == name]


def dataset_url(dataset_id):
    """Power BI datasets API URL for a model in My workspace (no /groups/{id} part for personal workspaces)."""
    return f"{PBI}/datasets/{dataset_id}"


def definition_parts(folder, include):
    """Base64-encode the files under `folder` whose relative path starts with one of `include`."""
    folder = Path(folder)
    parts = []
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_file() and any(rel == p or rel.startswith(p + "/") for p in include):
            parts.append({"path": rel, "payload": base64.b64encode(path.read_bytes()).decode("ascii"),
                          "payloadType": "InlineBase64"})
    return parts
