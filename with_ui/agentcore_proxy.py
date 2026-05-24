from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

class AgentCoreProxy:
    """Proxy client for an already-hosted AgentCore runtime via `agentcore invoke`.

    Required env/config:
    - `agentcore` CLI installed
    - `.bedrock_agentcore.yaml` available in working directory
    - AWS credentials configured in environment/container
    """

    def __init__(self, workspace_dir: Path, agent_name: str | None = None) -> None:
        self.workspace_dir = workspace_dir
        self.agent_name = agent_name

    def invoke(self, prompt: str, actor_id: str, thread_id: str, agent_name: str | None = None) -> dict[str, Any]:
        payload = {"prompt": prompt, "actor_id": actor_id, "thread_id": thread_id}
        base_cmd = ["agentcore", "invoke", json.dumps(payload)]
        selected_agent = (agent_name or self.agent_name or "").strip()
        if selected_agent:
            base_cmd.extend(["--agent", selected_agent])

        self._debug(
            "invoke start "
            f"agent={selected_agent or 'default'!r} "
            f"workspace={str(self.workspace_dir)!r} payload={payload!r}"
        )

        attempts = [base_cmd]
        last_err = ""
        for cmd in attempts:
            try:
                return self._invoke_once(cmd, actor_id, thread_id, selected_agent)
            except Exception as exc:
                last_err = str(exc)
                self._debug(f"invoke attempt failed error={last_err!r}")
                continue
        raise RuntimeError(last_err or "agentcore invoke failed")

    def _invoke_once(self, cmd: list[str], actor_id: str, thread_id: str, selected_agent: str) -> dict[str, Any]:
        safe_cmd = [
            "<payload>" if i == 2 and part.startswith("{") else part
            for i, part in enumerate(cmd)
        ]
        self._debug(f"running command={safe_cmd!r}")
        proc = subprocess.run(
            cmd,
            cwd=str(self.workspace_dir),
            env={
                **os.environ,
                "AGENTCORE_SUPPRESS_RECOMMENDATION": "1",
            },
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_text = proc.stdout.strip()
        stderr_text = self._clean_stderr(proc.stderr)
        self._debug(f"returncode={proc.returncode}")
        if stdout_text:
            self._debug(f"raw stdout={self._shorten(stdout_text)!r}")
        if stderr_text:
            self._debug(f"stderr={self._shorten(stderr_text)!r}")

        if proc.returncode != 0:
            if stdout_text:
                data = self._extract_json_or_text(stdout_text)
                self._debug(f"parsed error stdout={self._shorten_repr(data)}")
                if data:
                    response = self._to_response(data, actor_id, thread_id, selected_agent)
                    self._debug(f"normalized response={self._shorten_repr(response)}")
                    return response
            raise RuntimeError(stderr_text or stdout_text or "agentcore invoke failed")

        data = self._extract_json_or_text(stdout_text)
        self._debug(f"parsed payload={self._shorten_repr(data)}")
        response = self._to_response(data, actor_id, thread_id, selected_agent)
        self._debug(f"normalized response={self._shorten_repr(response)}")
        return response

    @staticmethod
    def _debug(message: str) -> None:
        print(f"[AgentCoreProxy] {message}", flush=True)

    @staticmethod
    def _shorten(text: str, limit: int = 4000) -> str:
        if len(text) <= limit:
            return text
        return f"{text[:limit]}... [truncated {len(text) - limit} chars]"

    @staticmethod
    def _shorten_repr(value: Any, limit: int = 4000) -> str:
        return AgentCoreProxy._shorten(repr(value), limit=limit)

    @staticmethod
    def _to_response(
        data: dict[str, Any],
        actor_id: str,
        thread_id: str,
        agent_name: str
    ) -> dict[str, Any]:

        answer = AgentCoreProxy._extract_answer(data)

        if isinstance(answer, (dict, list)):
            answer = json.dumps(answer, ensure_ascii=False)

        if isinstance(answer, str):
            answer = AgentCoreProxy._normalize_text(answer)

        return {
            "answer": answer,
            "actor_id": actor_id,
            "thread_id": thread_id,
            "mode": "agentcore",
            "agent": agent_name or "default",
        }

    @staticmethod
    def _extract_answer(data: dict[str, Any]) -> Any:
        for key in ("answer", "result", "response", "output"):
            value = data.get(key)
            if value:
                if isinstance(value, str):
                    parsed = AgentCoreProxy._parse_payload(value)
                    if parsed and parsed is not data:
                        nested = AgentCoreProxy._extract_answer(parsed)
                        if nested:
                            return nested
                return value
        return "No response generated."

    @staticmethod
    def _clean_stderr(text: str) -> str:
        if not text:
            return ""
        lines = [
            ln
            for ln in text.splitlines()
            if "RequestsDependencyWarning" not in ln
            and "warnings.warn(" not in ln
            and "Invalid -W option ignored" not in ln
        ]
        return "\n".join([ln for ln in lines if ln.strip()]).strip()

    @staticmethod
    def _extract_json_or_text(text: str) -> dict[str, Any]:

        if not text:
            return {}

        # Remove ANSI escape sequences
        clean_text = re.sub(
            r"\x1b\[[0-9;]*[A-Za-z]",
            "",
            text
        )

        # Try extracting JSON after "Response:"
        response_match = re.search(
            r"Response:\s*(\{.*)",
            clean_text,
            flags=re.DOTALL
        )

        if response_match:

            payload_text = response_match.group(1).strip()

            # Extract balanced JSON only
            balanced = AgentCoreProxy._extract_balanced(payload_text)

            if balanced:

                try:
                    return json.loads(balanced, strict=False)
                except Exception:

                    try:
                        return ast.literal_eval(balanced)
                    except Exception:
                        pass

        # Fallback: find last JSON object
        matches = re.findall(
            r"(\{.*\})",
            clean_text,
            flags=re.DOTALL
        )

        for candidate in reversed(matches):

            try:
                return json.loads(candidate, strict=False)
            except Exception:
                continue

        # Final fallback
        return {
            "answer": "No response generated."
        }

    @staticmethod
    def _parse_payload(raw: str) -> dict[str, Any] | None:
        raw = raw.strip()
        if not raw:
            return None

        # Always isolate the first balanced JSON/Python container to avoid
        # parsing CLI wrapper text around the actual payload.
        container = None
        for opener in ("{", "["):
            idx = raw.find(opener)
            if idx >= 0:
                candidate = AgentCoreProxy._extract_balanced(raw[idx:])
                if candidate and (container is None or len(candidate) > len(container)):
                    container = candidate
        if container:
            raw = container

        try:
            data = json.loads(raw, strict=False)
            return AgentCoreProxy._normalize_payload(data)
        except json.JSONDecodeError:
            pass
        try:
            data = ast.literal_eval(raw)
            return AgentCoreProxy._normalize_payload(data)
        except Exception:
            return None

    @staticmethod
    def _normalize_payload(data: Any) -> dict[str, Any] | None:
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    @staticmethod
    def _extract_balanced(raw: str) -> str | None:
        opener = raw[0]
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        quote = ""
        escaped = False
        for i, ch in enumerate(raw):
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch == quote:
                    in_string = False
                continue
            if ch in ("'", '"'):
                in_string = True
                quote = ch
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return raw[: i + 1]
        return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        # Fix common mojibake from UTF-8 bytes interpreted as cp1252/latin-1.
        if any(token in text for token in ("â", "Ã", "â", "Â")):
            try:
                repaired = text.encode("latin-1").decode("utf-8")
                if repaired:
                    text = repaired
            except Exception:
                pass
        text = (
            text.replace("\u00a0", " ")
            .replace("\u202f", " ")
            .replace("\u2011", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )

        parsed = AgentCoreProxy._parse_payload(text)
        if parsed and isinstance(parsed.get("answer"), str):
            text = parsed["answer"]

        # UI renders plain text, so strip common markdown markers from model output.
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*]\s+", "- ", text, flags=re.MULTILINE)
        text = text.replace("  \n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
