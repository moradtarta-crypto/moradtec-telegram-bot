import os
import unittest
from unittest.mock import AsyncMock, patch

from shrtfly import _is_safe_destination, shorten_with_shrtfly


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response
        self.get = AsyncMock(return_value=response)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class ShrtFlyTests(unittest.IsolatedAsyncioTestCase):
    def test_accepts_public_https_destination(self):
        self.assertTrue(_is_safe_destination("https://deepai.org/video"))

    def test_rejects_non_https_and_local_destinations(self):
        self.assertFalse(_is_safe_destination("http://deepai.org/video"))
        self.assertFalse(_is_safe_destination("https://localhost/path"))
        self.assertFalse(_is_safe_destination("https://127.0.0.1/path"))

    async def test_returns_none_without_api_token_without_calling_api(self):
        with patch.dict(os.environ, {"SHRTFLY_API_TOKEN": ""}):
            with patch("shrtfly.httpx.AsyncClient") as client:
                result = await shorten_with_shrtfly("https://deepai.org/video")
        self.assertIsNone(result)
        client.assert_not_called()

    async def test_sends_expected_parameters_and_returns_short_url(self):
        response = FakeResponse({
            "status": "success",
            "result": {"shorten_url": "https://shrtslug.biz/abc123"},
        })
        client = FakeAsyncClient(response)
        with patch.dict(os.environ, {"SHRTFLY_API_TOKEN": "test-token"}):
            with patch("shrtfly.httpx.AsyncClient", return_value=client):
                result = await shorten_with_shrtfly("https://deepai.org/video")

        self.assertEqual(result, "https://shrtslug.biz/abc123")
        client.get.assert_awaited_once()
        args, kwargs = client.get.await_args
        self.assertEqual(args[0], "https://shrtfly.com/api")
        self.assertEqual(kwargs["params"]["api"], "test-token")
        self.assertEqual(kwargs["params"]["url"], "https://deepai.org/video")
        self.assertEqual(kwargs["params"]["type"], "1")
        self.assertEqual(kwargs["params"]["format"], "json")

    async def test_rejects_unexpected_short_link_host(self):
        response = FakeResponse({
            "status": "success",
            "result": {"shorten_url": "https://example.com/not-ours"},
        })
        client = FakeAsyncClient(response)
        with patch.dict(os.environ, {"SHRTFLY_API_TOKEN": "test-token"}):
            with patch("shrtfly.httpx.AsyncClient", return_value=client):
                result = await shorten_with_shrtfly("https://deepai.org/video")
        self.assertIsNone(result)

    async def test_returns_none_when_api_rejects_request(self):
        response = FakeResponse({"status": "error", "message": "invalid token"})
        client = FakeAsyncClient(response)
        with patch.dict(os.environ, {"SHRTFLY_API_TOKEN": "test-token"}):
            with patch("shrtfly.httpx.AsyncClient", return_value=client):
                result = await shorten_with_shrtfly("https://deepai.org/video")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
