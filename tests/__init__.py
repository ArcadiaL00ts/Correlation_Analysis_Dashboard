"""Test package. Blocks outbound network for the whole suite so tests stay offline and deterministic.

Loopback connections stay allowed. yfinance (curl_cffi) opens C-level sockets this guard cannot see,
so tests that touch prices mock yfinance instead. Set ``CORRDASH_TESTS_ALLOW_NETWORK=1`` to disable the guard.
"""

from __future__ import annotations

import os
import socket

os.environ.setdefault("DASHBOARD_SKIP_TLS_PROBE", "1")

if os.environ.get("CORRDASH_TESTS_ALLOW_NETWORK") != "1":
    _LOOPBACK = {"127.0.0.1", "::1", "localhost"}
    _original_connect = socket.socket.connect

    def _guarded_connect(self: socket.socket, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in _LOOPBACK:
            raise ConnectionError(f"Network access is blocked in tests (tried {address!r}).")
        return _original_connect(self, address, *args, **kwargs)

    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
