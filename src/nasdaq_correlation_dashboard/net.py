"""HTTPS trust setup for machines behind TLS-inspecting proxies or antivirus.

Two HTTP stacks fetch data: ``requests`` (Nasdaq, QQQM/Invesco) and ``curl_cffi`` (yfinance).
Both trust the ``certifi`` bundle by default, which lacks the private root that a corporate proxy
or an antivirus (e.g. Norton, Kaspersky, Zscaler) uses to re-sign HTTPS traffic. The symptom is
``CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`` on every fetch.

``configure_tls()`` runs once per process, before any fetch:

1. ``DASHBOARD_CA_BUNDLE`` set -> export it to ``SSL_CERT_FILE``, ``REQUESTS_CA_BUNDLE`` and
   ``CURL_CA_BUNDLE`` and stop.
2. Otherwise probe one HTTPS request. Success, or a non-TLS network failure, -> do nothing.
3. On a certificate failure: on Windows, build ``certifi`` + the Windows ROOT/CA stores into a
   cached PEM bundle and export the three variables. Elsewhere, try ``truststore`` (optional)
   and print how to set ``DASHBOARD_CA_BUNDLE``.

Certificate verification is never disabled.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable

CA_ENV_VARS: tuple[str, ...] = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")
OVERRIDE_ENV = "DASHBOARD_CA_BUNDLE"
SKIP_PROBE_ENV = "DASHBOARD_SKIP_TLS_PROBE"
PROBE_URL = "https://query1.finance.yahoo.com"
BUNDLE_MAX_AGE_SECONDS = 7 * 24 * 3600

_status: str | None = None


def _log(message: str) -> None:
    print(f"[tls] {message}", file=sys.stderr)


def export_ca_bundle(bundle: Path | str) -> None:
    for name in CA_ENV_VARS:
        os.environ[name] = str(bundle)


def default_bundle_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "nasdaq-correlation-dashboard" / "ca_bundle.pem"


def probe_https(url: str = PROBE_URL, timeout: float = 5.0) -> str:
    """Return ``"ok"``, ``"cert_error"`` or ``"network_error"``."""
    import requests

    try:
        requests.head(url, timeout=timeout, allow_redirects=False)
    except requests.exceptions.SSLError as exc:
        return "cert_error" if "CERTIFICATE_VERIFY_FAILED" in str(exc) else "network_error"
    except requests.exceptions.RequestException:
        return "network_error"
    return "ok"


def _windows_store_pems(enum_certificates: Callable[[str], list] | None = None) -> list[str]:
    import ssl

    enum = enum_certificates or getattr(ssl, "enum_certificates", None)
    if enum is None:
        return []
    pems: list[str] = []
    seen: set[bytes] = set()
    for store in ("ROOT", "CA"):
        try:
            entries = enum(store)
        except OSError:
            continue
        for der, encoding, _trust in entries:
            if encoding != "x509_asn" or der in seen:
                continue
            seen.add(der)
            pems.append(ssl.DER_cert_to_PEM_cert(der))
    return pems


def build_windows_bundle(
    target: Path | None = None,
    *,
    enum_certificates: Callable[[str], list] | None = None,
    max_age_seconds: int = BUNDLE_MAX_AGE_SECONDS,
) -> Path:
    """Write certifi + Windows certificate stores to ``target``; reuse a fresh cached copy."""
    import certifi

    target = target or default_bundle_path()
    if target.exists() and (time.time() - target.stat().st_mtime) < max_age_seconds:
        return target
    store_pems = _windows_store_pems(enum_certificates)
    content = Path(certifi.where()).read_text(encoding="ascii").rstrip() + "\n"
    content += "\n# --- Windows certificate store (ROOT + CA) ---\n" + "".join(store_pems)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(content, encoding="ascii")
    os.replace(tmp, target)
    return target


def configure_tls(
    *,
    probe: Callable[[], str] | None = None,
    platform: str | None = None,
    force: bool = False,
) -> str:
    """Make HTTPS work for requests and yfinance. Returns what was done (for logs and tests).

    Values: ``"override"``, ``"skipped"``, ``"ok"``, ``"offline"``, ``"windows_bundle"``,
    ``"truststore"``, ``"unresolved"``.
    """
    global _status
    if _status is not None and not force:
        return _status

    override = os.environ.get(OVERRIDE_ENV, "").strip()
    if override:
        if not Path(override).is_file():
            _log(f"{OVERRIDE_ENV}={override} does not exist; HTTPS may fail.")
        export_ca_bundle(override)
        _status = "override"
        return _status

    if os.environ.get(SKIP_PROBE_ENV, "").strip().lower() in {"1", "true", "yes"}:
        _status = "skipped"
        return _status

    run_probe = probe or probe_https
    result = run_probe()
    if result == "ok":
        _status = "ok"
        return _status
    if result != "cert_error":
        _status = "offline"
        return _status

    platform = platform or sys.platform
    if platform == "win32":
        try:
            bundle = build_windows_bundle()
        except Exception as exc:  # noqa: BLE001 - report and continue; fetches will show the real error
            _log(f"Could not build a CA bundle from the Windows certificate store: {exc}")
        else:
            export_ca_bundle(bundle)
            if run_probe() == "ok":
                _log(
                    "HTTPS is being inspected by a proxy or antivirus; using the Windows certificate "
                    f"store via {bundle}."
                )
                _status = "windows_bundle"
                return _status

    try:
        import truststore  # type: ignore[import-not-found]

        truststore.inject_into_ssl()
        if run_probe() == "ok":
            _log("Using the operating-system trust store via truststore (requests only).")
            _status = "truststore"
            return _status
    except ImportError:
        pass

    _log(
        "HTTPS certificate verification failed (a proxy or antivirus is probably inspecting traffic). "
        f"Export your organisation's root certificate as PEM and set {OVERRIDE_ENV} to its path."
    )
    _status = "unresolved"
    return _status
