"""Guarded AI code-proposal workflow for the MoradTec Telegram bot.

Generated source is isolated under ai_proposals/, syntax-checked and screened
before it is committed to a dedicated branch and opened as a draft pull request.
It is never imported into or executed by the live bot.
"""
from __future__ import annotations

import ast
import base64
from datetime import datetime, timezone
import hashlib
import os
import re

import httpx

EXPECTED_REPOSITORY = "moradtarta-crypto/moradtec-telegram-bot"
TEXT_MODEL = "@cf/meta/llama-3.2-3b-instruct"
ALLOWED_IMPORTS = {
    "collections", "datetime", "decimal", "functools", "itertools",
    "json", "math", "re", "statistics", "string", "typing",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "open", "__import__", "breakpoint"}
FORBIDDEN_ATTRIBUTES = {
    "__globals__", "__builtins__", "__subclasses__", "__mro__",
    "system", "popen", "spawn", "fork", "execv", "execve",
}
MAX_SOURCE_CHARS = 12000


class ProposalValidationError(ValueError):
    """Raised when generated source fails the proposal safety checks."""


def clean_generated_source(raw: str) -> str:
    """Remove a single outer Markdown fence, if the model added one."""
    source = (raw or "").strip()
    fence = chr(96) * 3
    if source.startswith(fence):
        lines = source.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == fence:
            source = "\n".join(lines[1:-1]).strip()
    return source + ("\n" if source and not source.endswith("\n") else "")


def validate_generated_python(raw: str) -> str:
    """Accept only bounded, parseable, isolated Python proposal source."""
    source = clean_generated_source(raw)
    if not source or len(source) > MAX_SOURCE_CHARS:
        raise ProposalValidationError("The generated proposal is empty or exceeds the size limit.")
    if re.search(r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{20,})", source):
        raise ProposalValidationError("The generated proposal appears to contain a credential.")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ProposalValidationError("The generated proposal has invalid Python syntax.") from exc

    has_definition = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            has_definition = True
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".")[0] for alias in node.names]
            if any(module not in ALLOWED_IMPORTS for module in modules):
                raise ProposalValidationError("The proposal imports a module outside the restricted allowlist.")
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in ALLOWED_IMPORTS:
                raise ProposalValidationError("The proposal imports a module outside the restricted allowlist.")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise ProposalValidationError("The proposal contains a forbidden dynamic or file operation.")
            if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_ATTRIBUTES:
                raise ProposalValidationError("The proposal contains a forbidden system or introspection operation.")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            raise ProposalValidationError("The proposal contains a forbidden system or introspection attribute.")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ProposalValidationError("Global state changes are not allowed in isolated proposals.")

    if not has_definition:
        raise ProposalValidationError("The proposal must define at least one function or class.")
    return source


async def _generate_source(goal: str, account_id: str, api_token: str) -> str:
    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/"
        f"{TEXT_MODEL}"
    )
    system = (
        "You are a cautious Python engineer. Produce one small, useful, self-contained "
        "Python module proposal for a Telegram bot project. Return ONLY Python source, "
        "not Markdown. Include a module docstring, type hints, and at least one function. "
        "Do not import os, pathlib, subprocess, socket, requests, httpx, telegram, or any "
        "third-party package. Allowed imports: collections, datetime, decimal, functools, "
        "itertools, json, math, re, statistics, string, typing. Do not read or write files, "
        "use network access, inspect environment variables, execute dynamic code, or access "
        "credentials. Keep the code under 250 lines and focus on the requested goal."
    )
    user = f"Create a review-only code proposal for this goal: {goal}"
    async with httpx.AsyncClient(timeout=55.0) as client:
        response = await client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_token}"},
            json={
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 1800,
                "temperature": 0.15,
            },
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", {})
        source = result.get("response", "") if isinstance(result, dict) else ""
        if not isinstance(source, str):
            raise RuntimeError("The AI provider returned an unsupported response.")
        return source


async def create_code_proposal(goal: str) -> dict[str, str]:
    """Generate, validate, and publish a review-only code proposal as a draft PR."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()

    if repository != EXPECTED_REPOSITORY:
        raise RuntimeError("GITHUB_REPOSITORY is missing or does not match the approved repository.")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not configured in the hosting environment.")
    if not account_id or not api_token:
        raise RuntimeError("Workers AI credentials are not configured in the hosting environment.")

    raw_source = await _generate_source(goal, account_id, api_token)
    source = validate_generated_python(raw_source)

    slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")[:24] or "improvement"
    digest = hashlib.sha256(goal.encode("utf-8")).hexdigest()[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    branch_name = f"ai-proposal/{stamp}-{digest}"
    filename = f"proposal_{stamp.replace('-', '_')}_{digest}.py"
    path = f"ai_proposals/{filename}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MoradTec-Safe-Code-Proposer",
    }
    api = f"https://api.github.com/repos/{EXPECTED_REPOSITORY}"

    try:
        async with httpx.AsyncClient(timeout=35.0, headers=headers) as client:
            repo_response = await client.get(api)
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            base = repo_data.get("default_branch")
            if base != "main":
                raise RuntimeError("The repository default branch is not the expected main branch.")

            ref_response = await client.get(f"{api}/git/ref/heads/{base}")
            ref_response.raise_for_status()
            base_sha = ref_response.json().get("object", {}).get("sha")
            if not base_sha:
                raise RuntimeError("Could not resolve the repository base commit.")

            create_ref = await client.post(
                f"{api}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )
            create_ref.raise_for_status()

            encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
            file_response = await client.put(
                f"{api}/contents/{path}",
                json={
                    "message": f"Add isolated AI proposal: {slug}",
                    "content": encoded,
                    "branch": branch_name,
                },
            )
            file_response.raise_for_status()

            pr_response = await client.post(
                f"{api}/pulls",
                json={
                    "title": f"[AI proposal] {goal[:65]}",
                    "head": branch_name,
                    "base": base,
                    "draft": True,
                    "body": (
                        "## AI-generated code proposal\n\n"
                        f"**Goal:** {goal}\n\n"
                        f"**Proposal file:** {path}\n\n"
                        "- Generated by Workers AI and checked for Python syntax.\n"
                        "- Restricted to an isolated ai_proposals/ file.\n"
                        "- The proposal is not imported or executed by the live bot.\n"
                        "- Review and run appropriate tests before considering integration.\n"
                        "- No automatic merge or deployment is performed.\n"
                    ),
                },
            )
            pr_response.raise_for_status()
            pr_data = pr_response.json()
            return {
                "url": pr_data.get("html_url", ""),
                "number": str(pr_data.get("number", "")),
                "branch": branch_name,
                "path": path,
            }
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            raise RuntimeError("GitHub rejected the token. Check its expiration and repository permissions.") from None
        if status == 403:
            raise RuntimeError("GitHub denied the operation. Check token permissions or API rate limits.") from None
        if status == 404:
            raise RuntimeError("GitHub could not find the repository or requested resource.") from None
        raise RuntimeError(f"GitHub API request failed with HTTP {status}.") from None
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Network error while contacting GitHub ({type(exc).__name__}).") from None
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("GitHub returned an invalid API response.") from None
