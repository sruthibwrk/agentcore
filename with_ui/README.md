# FAQ Assistant UI

Clean web chat UI for your deployed `002_agentcore_runtime_fast_embeddings.py` AgentCore runtime.

## Features

- Customer-friendly chat interface
- Hides AgentCore runtime details from the browser
- Displays only the assistant answer
- Cleans common Markdown markers from model output
- Pure AgentCore mode: UI only proxies chat to your hosted runtime
- FastAPI backend + static frontend in one app

## AgentCore-Hosted Mode

Use this when your agent is already deployed/hosted on AWS AgentCore and UI should only talk to it.

Set env vars:

```powershell
$env:AWS_REGION="us-east-1"
```

Then run:

```powershell
cd "C:\Users\kkapil\OneDrive - Sopra Steria\p\3. mlops\genai-projects\06_agentcore-crash-course-main\with_ui"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8090 --reload
```

Open:
- `http://localhost:8090`

Important:
- FAQ updates are done in your original code/redeployment path (same as your existing `agentcore invoke` workflow).
- UI does not replace your hosted agent; it only sends the prompt to it.
- This UI uses the same invocation path you used manually: `agentcore invoke ...`

## Run with Docker

From `with_ui`:

```powershell
docker compose up --build
```

Compose mounts these automatically:
- `../.bedrock_agentcore.yaml` -> `/app/.bedrock_agentcore.yaml`
- `${HOME}/.aws` -> `/root/.aws` (for AWS credentials/profile)
- App copies `.bedrock_agentcore.yaml` into writable `/tmp/agentcore_ui_runtime` before invoking `agentcore`.

Open:

- `http://localhost:8090`

## Notes

- This UI does not modify your original `bank_agent_agentcore_memory.py`.
- UI is a client proxy only; your hosted runtime does the reasoning/memory.
- Ensure `.bedrock_agentcore.yaml` and AWS credentials are valid for the container runtime.
