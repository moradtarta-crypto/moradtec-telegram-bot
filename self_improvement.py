"""Safe self-diagnostics and AI-assisted improvement planning for MoradTec.

This module is deliberately read-only: it inspects the running source tree and asks
Workers AI for recommendations. It never edits files, executes generated code, or
publishes to Telegram.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import httpx


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    severity: str = "warning"

    def as_dict(self) -> dict:
        return asdict(self)


def _parse_python(path: Path) -> tuple[ast.AST | None, str | None]:
    try:
        source = path.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(path)), None
    except (OSError, SyntaxError, UnicodeError) as exc:
        return None, type(exc).__name__


def run_self_check(project_root: str | Path = ".") -> list[Check]:
    """Run deterministic, offline checks. No source file is modified."""
    root = Path(project_root)
    bot_path = root / "bot.py"
    requirements_path = root / "requirements.txt"
    checks: list[Check] = []

    tree, parse_error = _parse_python(bot_path)
    checks.append(Check(
        "python_syntax",
        tree is not None,
        "bot.py syntax is valid." if tree is not None else f"Could not parse bot.py ({parse_error}).",
        "critical",
    ))
    if tree is None:
        return checks

    command_names = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_handler"
        and node.args
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "CommandHandler"
        and node.args[0].args
        and isinstance(node.args[0].args[0], ast.Constant)
        and isinstance(node.args[0].args[0].value, str)
    }
    required_commands = {"start", "help", "selfcheck", "improve"}
    missing = sorted(required_commands - command_names)
    checks.append(Check(
        "owner_tools_registered",
        not missing,
        "Self-improvement commands are registered." if not missing else "Missing command handlers: " + ", ".join(missing),
        "warning",
    ))

    source = bot_path.read_text(encoding="utf-8")
    has_owner_guard = "is_owner(update)" in source
    checks.append(Check(
        "owner_access_control",
        has_owner_guard,
        "Owner access checks are present." if has_owner_guard else "Could not find the owner access guard.",
        "critical",
    ))

    has_webhook_secret = "secret_token=WEBHOOK_SECRET" in source
    checks.append(Check(
        "webhook_secret",
        has_webhook_secret,
        "Telegram webhook secret validation is configured." if has_webhook_secret else "Webhook secret validation was not found.",
        "warning",
    ))

    required_env = ("BOT_TOKEN", "OWNER_ID", "CHANNEL_ID")
    missing_env = [key for key in required_env if not os.getenv(key)]
    checks.append(Check(
        "runtime_environment",
        not missing_env,
        "Required runtime environment variables are present." if not missing_env else "Missing runtime variables: " + ", ".join(missing_env),
        "critical",
    ))

    requirements_ok = requirements_path.is_file()
    checks.append(Check(
        "dependencies_manifest",
        requirements_ok,
        "requirements.txt exists." if requirements_ok else "requirements.txt is missing.",
        "warning",
    ))

    # Flag only obvious literal credentials; do not print matched values.
    literal_secret = re.search(
        r"""(?im)^\s*(?:BOT_TOKEN|CLOUDFLARE_API_TOKEN|GITHUB_TOKEN)\s*=\s*["'][^"']{12,}["']""",
        source,
    )
    checks.append(Check(
        "secret_hygiene",
        literal_secret is None,
        "No obvious hard-coded API token assignment was found." if literal_secret is None else "Possible hard-coded secret in bot.py; value hidden.",
        "critical",
    ))
    return checks


async def create_ai_improvement_plan(
    checks: Iterable[Check],
    goal: str = "",
    *,
    account_id: str | None = None,
    api_token: str | None = None,
) -> str | None:
    """Ask Workers AI for a concise plan based on diagnostics, not code execution."""
    account_id = (account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")).strip()
    api_token = (api_token or os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
    if not account_id or not api_token:
        return None

    findings = [check.as_dict() for check in checks]
    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/"
        "@cf/meta/llama-3.2-3b-instruct"
    )
    prompt = (
        "أنت مهندس برمجيات مسؤول عن مراجعة مساعد Telegram اسمه MoradTec. "
        "حلل نتائج الفحص التالية والهدف المطلوب. اكتب بالعربية خطة عملية قصيرة مرتبة حسب الأولوية. "
        "ميّز بين العيوب المؤكدة والاقتراحات. لا تدّع أنك نفذت أي تغيير. "
        "لا تطلب أسراراً أو رموز وصول. لا تقترح تعديل صلاحيات النشر التلقائي أو تجاوز فحوصات الأمان. "
        "لا تكتب كوداً ولا تنفذ أوامر. إذا لم توجد مشكلة مؤكدة فقل ذلك بوضوح.\n\n"
        f"الهدف: {goal or 'مراجعة عامة لصحة البوت'}\n"
        f"نتائج الفحص: {findings}"
    )
    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_token}"},
                json={
                    "messages": [
                        {"role": "system", "content": "أنت مراجع برمجيات حذر. لا تخترع نتائج فحص."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 550,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result", {})
            answer = result.get("response", "") if isinstance(result, dict) else ""
            if not isinstance(answer, str):
                return None
            answer = re.sub(r"\s+", " ", answer).strip()
            return answer[:2600] if len(answer) >= 40 else None
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        # Never log request headers or credential-bearing URLs.
        return f"تعذر الحصول على تحليل الذكاء الاصطناعي ({type(exc).__name__}). نتائج الفحص المحلي متاحة أعلاه."
