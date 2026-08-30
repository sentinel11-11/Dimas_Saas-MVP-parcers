"""Единая конфигурация прокси. Секреты только из окружения / .env."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _mask(value: str) -> str:
    if "@" in value:
        return value.split("@")[-1]
    return value


class ProxySettings:
    host: str = os.getenv("PROXY_HOST", "").strip()
    http_port: str = os.getenv("PROXY_HTTP_PORT", "1206").strip()
    socks_port: str = os.getenv("PROXY_SOCKS_PORT", "11206").strip()
    user: str = os.getenv("PROXY_USER", "").strip()
    password: str = os.getenv("PROXY_PASSWORD", "").strip()
    protocol: str = os.getenv("PROXY_PROTOCOL", "http").strip().lower()  # http | socks5

    @classmethod
    def enabled(cls) -> bool:
        return bool(cls.host and cls.http_port)

    @classmethod
    def http_url(cls) -> Optional[str]:
        if not cls.enabled():
            extra = os.getenv("AVITO_PROXIES") or os.getenv("AUTORU_PROXIES") or ""
            first = extra.split(",")[0].strip()
            if first:
                if "://" not in first:
                    return f"http://{first}"
                return first
            return None
        user = quote(cls.user, safe="") if cls.user else ""
        password = quote(cls.password, safe="") if cls.password else ""
        auth = f"{user}:{password}@" if cls.user else ""
        return f"http://{auth}{cls.host}:{cls.http_port}"

    @classmethod
    def socks_url(cls) -> Optional[str]:
        if not cls.enabled():
            return None
        user = quote(cls.user, safe="") if cls.user else ""
        password = quote(cls.password, safe="") if cls.password else ""
        auth = f"{user}:{password}@" if cls.user else ""
        return f"socks5://{auth}{cls.host}:{cls.socks_port}"

    @classmethod
    def requests_proxies(cls) -> Dict[str, str]:
        if cls.protocol == "socks5":
            url = cls.socks_url()
        else:
            url = cls.http_url()
        if not url:
            return {}
        logger.info(f"HTTP client proxy host: {_mask(url)}")
        return {"http": url, "https": url}

    @classmethod
    def proxy_list(cls) -> List[str]:
        url = cls.http_url()
        return [url] if url else []

    @classmethod
    def playwright_proxy(cls) -> Optional[Dict[str, str]]:
        """Playwright: server без логина в URL + username/password отдельно."""
        if not cls.enabled():
            url = cls.http_url()
            if not url:
                return None
            if "@" in url:
                creds, host = url.split("@", 1)
                scheme = "http"
                if "://" in creds:
                    scheme, creds = creds.split("://", 1)
                user, _, password = creds.partition(":")
                return {
                    "server": f"{scheme}://{host}",
                    "username": user,
                    "password": password,
                }
            return {"server": url}
        scheme = "socks5" if cls.protocol == "socks5" else "http"
        port = cls.socks_port if scheme == "socks5" else cls.http_port
        cfg = {"server": f"{scheme}://{cls.host}:{port}"}
        if cls.user:
            cfg["username"] = cls.user
            cfg["password"] = cls.password
        logger.info(f"Playwright proxy: {scheme}://{cls.host}:{port}")
        return cfg
