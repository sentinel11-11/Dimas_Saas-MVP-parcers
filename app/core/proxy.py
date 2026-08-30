"""Единая конфигурация прокси. Секреты только из окружения / .env."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _mask(value: str) -> str:
    if "@" in value:
        return value.split("@")[-1]
    return value


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


class ProxySettings:
    @classmethod
    def reload(cls) -> None:
        load_dotenv(ROOT / ".env", override=False)

    @classmethod
    def host(cls) -> str:
        return _env("PROXY_HOST")

    @classmethod
    def http_port(cls) -> str:
        return _env("PROXY_HTTP_PORT", "1206")

    @classmethod
    def socks_port(cls) -> str:
        return _env("PROXY_SOCKS_PORT", "11206")

    @classmethod
    def user(cls) -> str:
        return _env("PROXY_USER")

    @classmethod
    def password(cls) -> str:
        return _env("PROXY_PASSWORD")

    @classmethod
    def protocol(cls) -> str:
        return _env("PROXY_PROTOCOL", "http").lower()

    @classmethod
    def enabled(cls) -> bool:
        return bool(cls.http_url())

    @classmethod
    def http_url(cls) -> Optional[str]:
        if cls.host() and cls.http_port():
            user = quote(cls.user(), safe="") if cls.user() else ""
            password = quote(cls.password(), safe="") if cls.password() else ""
            auth = f"{user}:{password}@" if cls.user() else ""
            return f"http://{auth}{cls.host()}:{cls.http_port()}"
        extra = _env("AVITO_PROXIES") or _env("AUTORU_PROXIES")
        first = extra.split(",")[0].strip()
        if not first:
            return None
        if "://" not in first:
            return f"http://{first}"
        return first

    @classmethod
    def socks_url(cls) -> Optional[str]:
        if not cls.host():
            return None
        user = quote(cls.user(), safe="") if cls.user() else ""
        password = quote(cls.password(), safe="") if cls.password() else ""
        auth = f"{user}:{password}@" if cls.user() else ""
        return f"socks5://{auth}{cls.host()}:{cls.socks_port()}"

    @classmethod
    def requests_proxies(cls) -> Dict[str, str]:
        url = cls.socks_url() if cls.protocol() == "socks5" else cls.http_url()
        if not url:
            logger.warning("Proxy OFF: нет PROXY_HOST и нет AVITO_PROXIES в .env")
            return {}
        logger.info(f"HTTP client proxy host: {_mask(url)}")
        return {"http": url, "https": url}

    @classmethod
    def proxy_list(cls) -> List[str]:
        url = cls.http_url()
        return [url] if url else []

    @classmethod
    def status_line(cls) -> str:
        url = cls.http_url()
        if not url:
            return "Proxy: OFF  (создайте .env с PROXY_HOST / PROXY_USER / PROXY_PASSWORD)"
        return f"Proxy: ON  {_mask(url)}"

    @classmethod
    def playwright_proxy(cls, scheme: Optional[str] = None) -> Optional[Dict[str, str]]:
        if cls.host() and cls.http_port():
            # Chromium/Playwright cannot send SOCKS5 username/password.
            scheme = "http"
            port = cls.http_port()
            cfg = {"server": f"{scheme}://{cls.host()}:{port}"}
            if cls.user():
                cfg["username"] = cls.user()
                cfg["password"] = cls.password()
            logger.info(f"Playwright proxy: {scheme}://{cls.host()}:{port}")
            return cfg
        url = cls.http_url()
        if not url:
            logger.warning("Playwright proxy OFF")
            return None
        if "@" in url:
            creds, host = url.split("@", 1)
            scheme = "http"
            if "://" in creds:
                scheme, creds = creds.split("://", 1)
            user, _, password = creds.partition(":")
            logger.info(f"Playwright proxy: {scheme}://{host}")
            return {"server": f"{scheme}://{host}", "username": user, "password": password}
        return {"server": url}
