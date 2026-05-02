"""Cookie 解析工具"""
from __future__ import annotations

from http.cookiejar import CookieJar

try:
    from aiohttp import hdrs
    from aiohttp import ClientResponse
except ImportError:
    hdrs = None
    ClientResponse = None


def parse_cookie_string(cookie_string: str) -> CookieJar:
    """解析 cookie 字符串为 CookieJar"""
    jar = CookieJar()
    for part in cookie_string.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        value = value.strip()
        # 跳过无效 cookie
        if not name or name.lower() in ("path", "domain", "expires", "secure", "httponly"):
            continue
        from http.cookiejar import Cookie
        import time
        c = Cookie(
            version=0,
            name=name,
            value=value,
            port=None,
            port_specified=False,
            domain="",
            domain_specified=False,
            domain_initial_dot=False,
            path="/",
            path_specified=True,
            secure=False,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        jar.set_cookie(c)
    return jar
