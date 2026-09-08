from app.core.proxy import ProxySettings, _mask


def test_mask_hides_credentials():
    assert _mask("user435202:secret@185.81.147.98:1206") == "185.81.147.98:1206"


def test_playwright_proxy_separates_auth():
    if not ProxySettings.host:
        return
    cfg = ProxySettings.playwright_proxy()
    assert "server" in cfg
    assert ProxySettings.password not in cfg["server"]
