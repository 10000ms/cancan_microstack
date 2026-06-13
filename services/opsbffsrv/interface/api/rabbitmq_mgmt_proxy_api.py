import base64
import functools
import http
import json
import re
from typing import Awaitable, Callable, Optional

from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response

from linglong_web.utils import logger
from linglong_web import build_success_response
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import http_client
from linglong_web import LinglongConfig


def _allowed_cors_origins() -> set[str]:
    """读取配置的跨域白名单 / Read configured cross-origin allowlist."""
    raw = getattr(LinglongConfig, "PROXY_CORS_ALLOWED_ORIGINS", "") or ""
    return {o.strip() for o in raw.split(",") if o.strip()}


def _hardened_proxy_cors(func: Callable[..., Awaitable[Response]]):
    """安全的代理 CORS 装饰器（替代 linglong_web.allow_cors_specific）。

    Hardened CORS for proxy handlers, replacing the reflective
    ``allow_cors_specific`` (which echoed any Origin AND set
    Allow-Credentials:true AND stripped CSP/X-Frame-Options).

    安全权衡 / Security tradeoffs:
    - 同源访问（无 Origin 头）不下发任何 CORS 头，正常工作。
    - 仅当请求 Origin 命中显式白名单时，才回显该 Origin 并允许带凭证；
      绝不出现 "反射任意 Origin + Allow-Credentials:true" 组合（CSRF/凭证泄露风险）。
    - 不在白名单内的跨域请求不下发 CORS 头（浏览器自行拦截）。
    - 不再无差别删除 CSP / X-Frame-Options（由下游 handler 自己按需最小调整）。
    """

    @functools.wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        request_origin = request.headers.get("Origin") or request.headers.get("origin")
        allowlist = _allowed_cors_origins()
        origin_allowed = bool(request_origin) and request_origin in allowlist

        cors_headers: dict[str, str] = {}
        if origin_allowed:
            # 白名单命中：回显具体 Origin（非 "*"），可安全带凭证。
            cors_headers = {
                "Access-Control-Allow-Origin": request_origin,
                "Vary": "Origin",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": (
                    "Authorization, Content-Type, X-Requested-With, x-forwarded-uri, "
                    "x-forwarded-proto, x-forwarded-host, x-forwarded-port, x-original-uri"
                ),
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400",
            }

        if request.method == "OPTIONS":
            # 同源 / 非白名单跨域：返回 204 但不下发放行头，浏览器自行处理。
            return Response(status_code=204, headers=cors_headers)

        response = await func(request, *args, **kwargs)

        if isinstance(response, Response):
            for key, value in cors_headers.items():
                response.headers[key] = value

        return response

    return wrapper


@_hardened_proxy_cors
async def rabbitmq_mgmt_proxy_handler(request: Request) -> Response:
    """RabbitMQ Management 代理处理器"""
    original_path = request.url.path

    # 1. 根路径强制加斜杠，防止静态资源路径错误
    if original_path.endswith("/rabbitmq_mgmt") and not original_path.endswith("/rabbitmq_mgmt/"):
        return RedirectResponse(url=f"{request.url}/", status_code=301)

    proxy_path = original_path.replace("/v1/opsbffsrv/rabbitmq_mgmt", "", 1) or "/"
    base_url = (LinglongConfig.RABBITMQ_MGMT_BASE_URL or "").rstrip("/")
    target_url = f"{base_url}{proxy_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    logger.debug(f"[RabbitMQ Proxy] {request.method} {proxy_path} -> {target_url}")

    # 2. 准备请求头
    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('content-length', None)  # 让 httpx 重新计算

    # 【核心逻辑】：后端真替换
    # 无论前端传什么 Authorization (包括我们注入的假 Token)，全部清洗掉
    # 强制换成 RabbitMQ 真正的 Admin 账号
    headers.pop('authorization', None)
    headers.pop('Authorization', None)
    _inject_real_basic_auth(headers)

    body = await request.body() if request.method in {"POST", "PUT", "PATCH"} else None

    try:
        resp = await http_client.fetch(
            method=request.method,
            url=target_url,
            format_type="raw",  # 透传二进制资源，避免对图片/字体等做 text decode / passthrough binary safely
            headers=headers,
            data=body,
            timeout=30.0,
            passthrough_errors=True,
        )

        content = await resp.read()

        # 3. 处理响应头
        # 仅剥离破坏透传的 hop-by-hop / 长度 / 编码相关头。
        # 保留 X-Content-Type-Options / X-Frame-Options 等安全头（不再无差别删除）。
        # Only strip hop-by-hop / length / encoding headers that break passthrough.
        # Keep security headers like X-Content-Type-Options / X-Frame-Options intact.
        hop_by_hop_headers = [
            'transfer-encoding', 'content-encoding', 'connection', 'content-length',
        ]
        response_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in hop_by_hop_headers
        }

        # 4. 【核心逻辑】：对所有 HTML 页面注入脚本（RabbitMQ 4 可能有多个入口页面）
        # Inject into ALL HTML pages to ensure login bypass works regardless of entry point
        content_type = _get_header_case_insensitive(response_headers, "content-type")
        is_html_response = "text/html" in content_type.lower()
        if is_html_response:
            logger.debug(f"[RabbitMQ Proxy] Injecting auto-login script into HTML: {proxy_path}")
            content = _inject_auto_login_script(content)
            # 注入后内容长度变了，必须删除 Content-Length 让服务器自动处理
            response_headers.pop("Content-Length", None)
            # 安全权衡 / Security tradeoff:
            # 我们向 HTML 注入了内联 login-bypass 脚本。若上游 RabbitMQ 下发了
            # 限制性 CSP（默认通常没有），它会阻断该内联脚本，导致免登录失效。
            # 因此仅在「确实注入」的 HTML 响应上移除上游 CSP；其余响应（API/JSON/
            # 静态资源）保留 CSP。X-Frame-Options 始终保留。
            # We inject an inline login-bypass script into HTML. A restrictive upstream
            # CSP (rare for RabbitMQ mgmt UI) would block it, breaking the bypass.
            # So we drop the upstream CSP ONLY on HTML responses we actually inject into;
            # all other responses keep their CSP. X-Frame-Options is always preserved.
            for csp_key in ("content-security-policy", "Content-Security-Policy"):
                response_headers.pop(csp_key, None)

        # 注入判定诊断头，便于线上快速确认是否命中注入分支
        # Diagnostic headers for quick runtime verification of injection decision
        response_headers["X-OpsBFF-RMQ-Injected"] = "1" if is_html_response else "0"
        response_headers["X-OpsBFF-RMQ-ContentType"] = content_type or "-"

        return Response(content=content, status_code=resp.status, headers=response_headers)

    except Exception as e:
        logger.error(f"Proxy Error: {e}")
        raise HTTPException(status_code=502, msg="RabbitMQ Gateway Error")


def _inject_real_basic_auth(headers: dict):
    """注入真正的 RabbitMQ 账号密码"""
    username = LinglongConfig.RABBITMQ_MGMT_USERNAME
    password = LinglongConfig.RABBITMQ_MGMT_PASSWORD
    if username and password:
        token = base64.b64encode(f"{username}:{password}".encode("latin1")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"


def _get_header_case_insensitive(headers: dict, header_name: str) -> str:
    """按大小写不敏感方式读取响应头。
    Read response header value in case-insensitive way.
    """

    target = header_name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return str(value)
    return ""


def _inject_auto_login_script(html_content: bytes) -> bytes:
    html_str = html_content.decode("utf-8", errors="replace")

    # RabbitMQ UI 使用 localStorage 的 auth，并通过 XHR 发送 Authorization。
    # RabbitMQ UI stores auth in localStorage and sends it via XHR Authorization header.
    #
    # 安全说明 / Security note:
    # - 这里不向浏览器暴露真实账号密码。
    # - 代理层会强制清洗 Authorization 并注入真实 BasicAuth。
    # - 只要 UI 认为"有 auth"，就不会跳登录页。
    try:
        dummy_user = getattr(LinglongConfig, "DUMMY_USER", None) or "ops_user"
    except Exception:
        dummy_user = "ops_user"

    try:
        dummy_auth_token = getattr(LinglongConfig, "DUMMY_AUTH_TOKEN", None) or ""
    except Exception:
        dummy_auth_token = ""

    if not dummy_auth_token:
        try:
            dummy_pass = getattr(LinglongConfig, "DUMMY_PASS", None) or "dummy_pass"
        except Exception:
            dummy_pass = "dummy_pass"
        token = base64.b64encode(f"{dummy_user}:{dummy_pass}".encode("latin1")).decode("ascii")
        dummy_auth_token = f"Basic {token}"

    credentials = dummy_auth_token.replace("Basic ", "", 1).strip()

    # 构造注入脚本 - 增强版，支持 RabbitMQ 3.x 和 4.x
    # Enhanced script supporting both RabbitMQ 3.x and 4.x
    injection = f"""
    <script>
    (function() {{
        console.log('[OpsBFF] 🚀 Injecting Credentials & Bypassing Login (Enhanced for RMQ 3.x/4.x)...');

        var FAKE_AUTH = '{dummy_auth_token}';
        var FAKE_CREDENTIALS = '{credentials}';
        var FAKE_SCHEME = 'Basic';
        var FAKE_USER = '{dummy_user}';

        function shortKey(str) {{
            var hash = 0;
            if (!str || str.length === 0) return '0';
            for (var i = 0; i < str.length; i++) {{
                hash = (31 * hash + str.charCodeAt(i)) | 0;
            }}
            var shortHash = Math.abs((hash << 16) >> 16);
            return shortHash.toString(16);
        }}

        function parseCookieM() {{
            var cookies = document.cookie ? document.cookie.split(';') : [];
            var m = '';
            for (var i = 0; i < cookies.length; i++) {{
                var parts = cookies[i].trim().split('=');
                if (parts[0] === 'm') {{
                    m = parts.slice(1).join('=');
                    break;
                }}
            }}
            var dict = {{}};
            if (!m) return dict;
            var items = m.split('|');
            for (var j = 0; j < items.length; j++) {{
                if (!items[j]) continue;
                var kv = items[j].split(':');
                if (kv.length >= 2) {{
                    var key = kv[0];
                    var value = decodeURIComponent(kv.slice(1).join(':'));
                    dict[key] = value;
                }}
            }}
            return dict;
        }}

        function writeCookieM(dict, expiresAt) {{
            var enc = [];
            for (var k in dict) {{
                if (!Object.prototype.hasOwnProperty.call(dict, k)) continue;
                enc.push(k + ':' + encodeURIComponent(String(dict[k])));
            }}
            document.cookie = 'm=' + enc.join('|') + '; expires=' + expiresAt.toUTCString() + '; path=/';
        }}

        function seedLoggedInCookie() {{
            try {{
                var dict = parseCookieM();
                dict[shortKey('loggedIn')] = 'true';
                dict[shortKey('login_session_timeout')] = '480';
                var expiry = new Date();
                expiry.setHours(expiry.getHours() + 8);
                writeCookieM(dict, expiry);
            }} catch (e) {{
                console.error('[OpsBFF] Cookie seed error:', e);
            }}
        }}

        // 1. 强制写入 LocalStorage 和 SessionStorage (覆盖 RabbitMQ 3.x 和 4.x 的 keys)
        // Force write to both LocalStorage and SessionStorage (covers RMQ 3.x and 4.x keys)
        function credentialsSeeded() {{
            try {{
                // Minimal readiness check: once these are present, RMQ UI can proceed.
                // 最小就绪判断：这些 key 存在后，UI 的 prefs/auth 读取即可正常继续。
                return (
                    localStorage.getItem('rabbitmq.credentials') === FAKE_CREDENTIALS &&
                    localStorage.getItem('rabbitmq.auth-scheme') === FAKE_SCHEME &&
                    (localStorage.getItem('auth') === FAKE_AUTH || sessionStorage.getItem('auth') === FAKE_AUTH)
                );
            }} catch (e) {{
                return false;
            }}
        }}

        function seedCredentials() {{
            try {{
                // RabbitMQ 4.x required keys (prefs.js contract)
                localStorage.setItem('rabbitmq.credentials', FAKE_CREDENTIALS);
                localStorage.setItem('rabbitmq.auth-scheme', FAKE_SCHEME);
                localStorage.setItem('rabbitmq.auth_resource', '/');

                // RabbitMQ 3.x keys
                localStorage.setItem('auth', FAKE_AUTH);
                localStorage.setItem('rabbitmq_current_user', FAKE_USER);
                localStorage.setItem('last_login', new Date().getTime());
                
                // RabbitMQ 4.x possible keys (auth may be stored differently)
                localStorage.setItem('rabbitmq.auth', FAKE_AUTH);
                localStorage.setItem('rabbitmq.user', FAKE_USER);
                localStorage.setItem('rabbitmq-auth', FAKE_AUTH);
                localStorage.setItem('user', FAKE_USER);
                
                // Also try sessionStorage for some RabbitMQ versions
                sessionStorage.setItem('auth', FAKE_AUTH);
                sessionStorage.setItem('rabbitmq_current_user', FAKE_USER);
                sessionStorage.setItem('rabbitmq.credentials', FAKE_CREDENTIALS);
                sessionStorage.setItem('rabbitmq.auth-scheme', FAKE_SCHEME);
                seedLoggedInCookie();

                // Avoid log spam: seed happens frequently during bootstrap.
                // 避免刷屏：初始化阶段会频繁 seed，这里只打印一次。
                try {{
                    if (!sessionStorage.getItem('opsbff-rmq-seed-log-once')) {{
                        sessionStorage.setItem('opsbff-rmq-seed-log-once', '1');
                        console.log('[OpsBFF] Credentials seeded to localStorage and sessionStorage.');
                    }}
                }} catch (e) {{}}
            }} catch(e) {{ console.error('[OpsBFF] Seed error:', e); }}
        }}
        seedCredentials();

        // 2) Patch XHR to always carry Authorization header.
        // RabbitMQ UI mainly uses jQuery/XHR for API calls.
        try {{
            var originalOpen = XMLHttpRequest.prototype.open;
            var originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(method, url) {{
                this.__opsbff_url = url;
                return originalOpen.apply(this, arguments);
            }};
            XMLHttpRequest.prototype.send = function(body) {{
                try {{
                    // Add a fake auth header; proxy will replace it with real BasicAuth.
                    this.setRequestHeader('Authorization', FAKE_AUTH);
                }} catch(e) {{}}
                return originalSend.apply(this, arguments);
            }};
            console.log('[OpsBFF] XHR patched.');
        }} catch(e) {{ console.error('[OpsBFF] XHR patch error:', e); }}

        // 3) Patch fetch for modern JS code
        try {{
            var originalFetch = window.fetch;
            if (originalFetch) {{
                window.fetch = function(url, options) {{
                    if (!options) options = {{}};
                    if (!options.headers) options.headers = {{}};
                    if (options.headers instanceof Headers) {{
                        options.headers.set('Authorization', FAKE_AUTH);
                    }} else {{
                        options.headers['Authorization'] = FAKE_AUTH;
                    }}
                    return originalFetch(url, options);
                }};
                console.log('[OpsBFF] Fetch patched.');
            }}
        }} catch(e) {{ console.error('[OpsBFF] Fetch patch error:', e); }}

        // 4) Route guard: if redirected to login page, force back to dashboard
        function enforceDashboard() {{
            var hash = window.location.hash.toLowerCase();
            var path = window.location.pathname.toLowerCase();
            var hasLoginForm = !!document.querySelector("input[name='username'], #login input, form[action*='login']");
            if (hash.includes('login') || path.includes('login')) {{
                console.log('[OpsBFF] Login redirect detected, forcing Dashboard...');
                seedCredentials(); // 再次写入，防止被清除
                if (hash.includes('login')) {{
                    window.location.hash = '#/';
                }} else {{
                    // For path-based login (RabbitMQ 4 might use this)
                    window.history.replaceState(null, '', window.location.origin + window.location.pathname.replace(/login.*/i, ''));
                }}
            }}

            if (hasLoginForm && !sessionStorage.getItem('opsbff-rmq-reload-once')) {{
                sessionStorage.setItem('opsbff-rmq-reload-once', '1');
                window.location.hash = '#/';
                window.location.reload();
            }}
        }}

        window.addEventListener('hashchange', enforceDashboard);
        window.addEventListener('popstate', enforceDashboard);
        
        // 定时轮询，防止初始化时的跳转
        var checkTimer = setInterval(function() {{
            enforceDashboard();
            // 持续写入防止被清除，但避免无意义的重复写入
            // Keep seeding during bootstrap, but skip when already present
            if (!credentialsSeeded()) {{
                seedCredentials();
            }}
        }}, 200);
        // 10秒后停止轮询，节省性能
        setTimeout(function() {{ clearInterval(checkTimer); }}, 10000);
        
        // 立即检查一次
        enforceDashboard();

    }})();
    </script>
    """

    head_match = re.search(r"<head[^>]*>", html_str, flags=re.IGNORECASE)
    if head_match:
        insert_at = head_match.end()
        return (html_str[:insert_at] + injection + html_str[insert_at:]).encode("utf-8")

    title_match = re.search(r"<title[^>]*>", html_str, flags=re.IGNORECASE)
    if title_match:
        insert_at = title_match.start()
        return (html_str[:insert_at] + injection + html_str[insert_at:]).encode("utf-8")

    return (injection + html_str).encode("utf-8")


async def rabbitmq_mgmt_login_bypass_probe_handler() -> APIResponse[dict]:
    """RabbitMQ Management 免登录状态探针。
    RabbitMQ Management login-bypass readiness probe.
    """

    base_url = (LinglongConfig.RABBITMQ_MGMT_BASE_URL or "").rstrip("/")
    upstream_whoami_url = f"{base_url}/api/whoami"
    upstream_root_url = f"{base_url}/"

    probe_result = {
        "base_url": base_url,
        "upstream_whoami_ok": False,
        "upstream_root_html_ok": False,
        "injector_contract_ok": False,
        "login_bypass_ready": False,
        "diagnostics": {
            "whoami_status": None,
            "whoami_body": None,
            "root_status": None,
            "root_content_type": None,
            "injector_markers": {},
        },
    }

    headers = {}
    _inject_real_basic_auth(headers)

    try:
        whoami_resp = await http_client.fetch(
            method=http.HTTPMethod.GET,
            url=upstream_whoami_url,
            headers=headers,
            timeout=15.0,
            passthrough_errors=True,
        )
        probe_result["diagnostics"]["whoami_status"] = whoami_resp.status

        whoami_text = await whoami_resp.text()
        probe_result["diagnostics"]["whoami_body"] = whoami_text[:256]
        if whoami_resp.status == http.HTTPStatus.OK:
            try:
                whoami_json = json.loads(whoami_text)
                probe_result["upstream_whoami_ok"] = bool(whoami_json.get("name"))
            except Exception:
                probe_result["upstream_whoami_ok"] = False
    except Exception as exc:  # noqa: BLE001
        probe_result["diagnostics"]["whoami_body"] = f"whoami probe failed: {exc}"

    try:
        root_resp = await http_client.fetch(
            method=http.HTTPMethod.GET,
            url=upstream_root_url,
            headers=headers,
            timeout=15.0,
            passthrough_errors=True,
        )
        probe_result["diagnostics"]["root_status"] = root_resp.status
        root_content_type = _get_header_case_insensitive(dict(root_resp.headers), "content-type")
        probe_result["diagnostics"]["root_content_type"] = root_content_type

        root_bytes = await root_resp.read()
        is_html = "text/html" in (root_content_type or "").lower()
        probe_result["upstream_root_html_ok"] = root_resp.status == http.HTTPStatus.OK and is_html

        injected = _inject_auto_login_script(root_bytes).decode("utf-8", errors="replace")
        markers = {
            "has_opsbff_marker": "[OpsBFF]" in injected,
            "has_rabbitmq_credentials_key": "rabbitmq.credentials" in injected,
            "has_rabbitmq_auth_scheme_key": "rabbitmq.auth-scheme" in injected,
            "has_logged_in_cookie_seed": "loggedIn" in injected and "document.cookie = 'm='" in injected,
        }
        probe_result["diagnostics"]["injector_markers"] = markers
        probe_result["injector_contract_ok"] = all(markers.values())
    except Exception as exc:  # noqa: BLE001
        probe_result["diagnostics"]["root_content_type"] = f"root probe failed: {exc}"

    probe_result["login_bypass_ready"] = bool(
        probe_result["upstream_whoami_ok"]
        and probe_result["upstream_root_html_ok"]
        and probe_result["injector_contract_ok"]
    )

    return build_success_response(data=probe_result)

