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
        node.args[0].args[0].value
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
    required_commands = {"start", "help", "selfcheck", "improve", "autodev"}
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


def _fallback_ai_report(checks: Iterable[Check], goal: str = "") -> str:
    """Produce a concise, factual Arabic report when model output is poor."""
    items = list(checks)
    failed = [item for item in items if not item.ok]
    if not failed:
        lines = ["المراجعة المحلية: جميع الفحوصات اجتازت الاختبار."]
        lines.append("لم تُسجل هذه الجولة مشكلة مؤكدة في الفحوصات السبعة.")
        if goal:
            lines.append(f"الهدف المطلوب: {goal[:180]}.")
        lines.append("هذه النتيجة لا تثبت خلو التطبيق من جميع الثغرات؛ إنها تغطي الفحوصات المحددة فقط.")
        return "\n".join(lines)
    lines = ["المشكلات المؤكدة في الفحص المحلي:"]
    for item in failed[:5]:
        lines.append(f"- {item.name}: {item.detail}")
    lines.append("ابدأ بمعالجة الفحوصات ذات الخطورة الحرجة، ثم أعد تشغيل /selfcheck.")
    return "\n".join(lines)


def _clean_ai_report(answer: str, checks: Iterable[Check], goal: str = "") -> str:
    """Remove repeated/garbled model output and reject claims unsupported by checks."""
    items = list(checks)
    # A green diagnostic run is deterministic evidence: do not let an LLM
    # invent failures, repair actions, or unrelated recommendations.
    if not any(not item.ok for item in items):
        return _fallback_ai_report(items, goal)
    checks = items
    if not isinstance(answer, str):
        return _fallback_ai_report(checks, goal)
    raw = answer.strip()
    if len(raw) < 40:
        return _fallback_ai_report(checks, goal)
    # Split on sentence boundaries, keeping Arabic and English punctuation.
    parts = re.split(r"(?<=[.!؟])\s+|[\r\n]+", raw)
    unique = []
    seen = set()
    for part in parts:
        part = re.sub(r"\s+", " ", part).strip(" -*•\t")
        if len(part) < 18:
            continue
        normalized = re.sub(r"[^\w]", "", part.casefold())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(part)
    if not unique:
        return _fallback_ai_report(checks, goal)
    # Repeated phrases or excessively long model responses are a quality failure.
    if len(unique) < 2 or len(unique) / max(1, len(parts)) < 0.55:
        return _fallback_ai_report(checks, goal)
    cleaned = " ".join(unique[:5])
    if len(cleaned) > 1100:
        cleaned = cleaned[:1097].rsplit(" ", 1)[0] + "..."
    return cleaned


async def create_ai_improvement_plan(
    checks: Iterable[Check],
    goal: str = "",
    *,
    account_id: str | None = None,
    api_token: str | None = None,
) -> str | None:
    """Ask Workers AI for a concise plan based on diagnostics, not code execution."""
    checks = list(checks)
    # No model call is needed when every deterministic check passed.
    if not any(not check.ok for check in checks):
        return _fallback_ai_report(checks, goal)

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
        "أنت مراجع برمجيات لمساعد Telegram اسمه MoradTec. "
        "اكتب بالعربية الفصحى الواضحة فقط. استخدم 3 إلى 5 جمل قصيرة، بحد أقصى 120 كلمة. "
        "ابدأ بذكر عدد الفحوصات الناجحة والفاشلة. إذا كانت كلها ناجحة، قل إنه لم تظهر مشكلة ضمن نطاق هذه الفحوصات، "
        "ولا تخترع عيوباً أو تكرر نصائح عامة. إذا فشل فحص، اذكر اسم الفحص وسبب الفشل كما ورد حرفياً ثم اقترح خطوة واحدة محددة. "
        "افصل بوضوح بين نتيجة مؤكدة واقتراح اختياري. لا تكرر الجمل أو العبارات. "
        "لا تستخدم تعبيرات مثل الملك أو الملكية الخاصة بالملك. لا تدّع تنفيذ أي تغيير. "
        "لا تطلب أسراراً أو رموز وصول، ولا تقترح تجاوز فحوصات الأمان أو تغيير صلاحيات النشر. "
        "أخرج التقرير فقط دون مقدمة مطولة.\n\n"
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
                    "max_tokens": 260,
                    "temperature": 0.0,
                },
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result", {})
            answer = result.get("response", "") if isinstance(result, dict) else ""
            if not isinstance(answer, str):
                return None
            answer = re.sub(r"\s+", " ", answer).strip()
            return _clean_ai_report(answer, checks, goal)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        # Never log request headers or credential-bearing URLs.
        return f"تعذر الحصول على تحليل الذكاء الاصطناعي ({type(exc).__name__}). نتائج الفحص المحلي متاحة أعلاه."
