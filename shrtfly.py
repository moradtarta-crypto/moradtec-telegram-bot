"""ShrtFly URL-shortening API integration for MoradTec."""
import ipaddress
import logging
import os
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("moradtec-bot.shrtfly")
API_ENDPOINT = "https://shrtfly.com/api"


def _is_safe_destination(url: str) -> bool:
    """Accept only public HTTPS destinations; reject local/private targets."""
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower().rstrip(".")
        try:
            address = ipaddress.ip_address(host)
            return address.is_global
        except ValueError:
            return "." in host and host not in {"localhost"}
    except (TypeError, ValueError):
        return False


async def shorten_with_shrtfly(url: str) -> str | None:
    """Create a monetized link; return None safely when unconfigured or unavailable."""
    token = os.getenv("SHRTFLY_API_TOKEN", "").strip()
    destination = (url or "").strip()
    if not token or not _is_safe_destination(destination):
        return None

    params = {
        "api": token,
        "url": destination,
        "type": "1",
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=7.0)) as client:
            response = await client.get(API_ENDPOINT, params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "success":
            logger.warning("ShrtFly API rejected a shortening request")
            return None
        result = payload.get("result")
        short_url = result.get("shorten_url") if isinstance(result, dict) else None
        if not isinstance(short_url, str):
            logger.warning("ShrtFly API response did not include a short URL")
            return None
        parsed = urlsplit(short_url)
        if parsed.scheme != "https" or parsed.hostname not in {"shrtfly.com", "www.shrtfly.com", "shrtslug.biz"}:
            logger.warning("ShrtFly API returned an unexpected short-link host")
            return None
        return short_url
    except httpx.HTTPStatusError as exc:
        logger.warning("ShrtFly API returned HTTP %s", exc.response.status_code)
    except httpx.RequestError as exc:
        logger.warning("ShrtFly API network error: %s", type(exc).__name__)
    except (ValueError, TypeError):
        logger.warning("ShrtFly API returned an invalid response")
    except Exception as exc:
        logger.warning("ShrtFly integration failed: %s", type(exc).__name__)
    return None
