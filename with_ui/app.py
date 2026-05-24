from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentcore_proxy import AgentCoreProxy


load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUNTIME_DIR = Path("/tmp/agentcore_ui_runtime")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AGENTCORE_AGENT = os.getenv("AGENTCORE_AGENT", "").strip() or None


def _prepare_writable_agentcore_workspace() -> Path:
    """Create writable workspace for `agentcore invoke`.

    The CLI mutates `.bedrock_agentcore.yaml` (e.g., session metadata), so
    using a read-only mounted config under /app will fail.
    """
    src_cfg = BASE_DIR / ".bedrock_agentcore.yaml"
    if not src_cfg.exists():
        src_cfg = BASE_DIR.parent / ".bedrock_agentcore.yaml"

    if not src_cfg.exists():
        raise RuntimeError(
            "Missing .bedrock_agentcore.yaml. Run agentcore configure from the course folder or mount it into the UI."
        )

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    dst_cfg = RUNTIME_DIR / ".bedrock_agentcore.yaml"
    if not dst_cfg.exists():
        shutil.copy2(src_cfg, dst_cfg)
    return RUNTIME_DIR


proxy = AgentCoreProxy(workspace_dir=_prepare_writable_agentcore_workspace(), agent_name=AGENTCORE_AGENT)

app = FastAPI(title="NeoBank Memory Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    actor_id: str = Field(default="web-user")
    thread_id: str = Field(default="web-chat")
    agent_id: str = Field(default="")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "mode": "agentcore", "region": AWS_REGION, "agent": AGENTCORE_AGENT or "default"}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    try:
        selected_agent = (req.agent_id or AGENTCORE_AGENT or "default").strip()
        print(
            "[UI API] chat request "
            f"agent={selected_agent!r} actor={req.actor_id!r} "
            f"thread={req.thread_id!r} prompt={req.prompt!r}",
            flush=True,
        )

        response = proxy.invoke(
            prompt=req.prompt,
            actor_id=req.actor_id,
            thread_id=req.thread_id,
            agent_name=req.agent_id or None,
        )

        ui_response = {
            "answer": response.get("answer", "No response generated.")
        }
        print(f"[UI API] response to browser={ui_response!r}", flush=True)
        return ui_response

    except Exception as exc:
        print(f"[UI API] chat failed: {exc}", flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {exc}"
        ) from exc
