"""Pure-logic network helpers (no Qt dependency).

These functions were extracted from MainWindow so they can be reused by
the runner and other non-UI code paths.
"""

import socket


def probe_tcp(host: str, port: int, timeout: float = 2.0) -> str:
    """Quick TCP connect test.

    Returns empty string on success, error message on failure.
    """
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return ""
    except socket.timeout:
        return f"连接超时 ({timeout}s) — 目标无响应"
    except ConnectionRefusedError:
        return "连接被拒绝 — 目标端口未监听"
    except OSError as e:
        return f"网络错误: {e}"


def diagnose_handshake_failure(err: str, sdk_name: str) -> str:
    """Suggest likely causes based on the handshake error message."""
    err_lower = err.lower()
    if "handshake failed" in err_lower or "did not respond" in err_lower:
        return (
            "提示: TCP 通但握手超时，常见原因:\n"
            f"  - 当前 SDK 选的是「{sdk_name}」，但设备运行的可能是另一种\n"
            "    尝试切换 SDK (Poco ↔ JX4) 后重连\n"
            "  - 设备上 Poco service 端口不是 13000\n"
            "  - service 已启动但未完成初始化"
        )
    if "connect failed" in err_lower:
        return "提示: TCP 层连接失败，请检查网络/防火墙"
    return ""
