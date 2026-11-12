from __future__ import annotations

import os
import ssl
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nasdaq_correlation_dashboard import net  # noqa: E402

# Any valid DER certificate works for the bundle test; take one from certifi.
import certifi  # noqa: E402

_FIRST_PEM = Path(certifi.where()).read_text(encoding="ascii").split("-----END CERTIFICATE-----")[0]
_FIRST_PEM += "-----END CERTIFICATE-----\n"
_FIRST_PEM = _FIRST_PEM[_FIRST_PEM.index("-----BEGIN CERTIFICATE-----"):]
SAMPLE_DER = ssl.PEM_cert_to_DER_cert(_FIRST_PEM)


class ConfigureTlsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        for name in (*net.CA_ENV_VARS, net.OVERRIDE_ENV, net.SKIP_PROBE_ENV):
            os.environ.pop(name, None)
        net._status = None

    def tearDown(self) -> None:
        self._env.stop()
        net._status = None

    def test_override_wins_without_probing(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as handle:
            path = handle.name
        self.addCleanup(os.unlink, path)
        os.environ[net.OVERRIDE_ENV] = path
        probe = mock.Mock(side_effect=AssertionError("must not probe"))
        self.assertEqual(net.configure_tls(probe=probe), "override")
        for name in net.CA_ENV_VARS:
            self.assertEqual(os.environ[name], path)

    def test_probe_ok_changes_nothing(self) -> None:
        self.assertEqual(net.configure_tls(probe=lambda: "ok"), "ok")
        for name in net.CA_ENV_VARS:
            self.assertNotIn(name, os.environ)

    def test_network_error_is_not_treated_as_tls(self) -> None:
        self.assertEqual(net.configure_tls(probe=lambda: "network_error"), "offline")
        self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_skip_env(self) -> None:
        os.environ[net.SKIP_PROBE_ENV] = "1"
        probe = mock.Mock(side_effect=AssertionError("must not probe"))
        self.assertEqual(net.configure_tls(probe=probe), "skipped")

    def test_result_is_cached_per_process(self) -> None:
        probe = mock.Mock(return_value="ok")
        net.configure_tls(probe=probe)
        net.configure_tls(probe=probe)
        self.assertEqual(probe.call_count, 1)

    def test_windows_cert_error_builds_bundle_and_reprobes(self) -> None:
        results = iter(["cert_error", "ok"])
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle.pem"
            with mock.patch.object(net, "build_windows_bundle", return_value=bundle) as build:
                status = net.configure_tls(probe=lambda: next(results), platform="win32")
            build.assert_called_once()
        self.assertEqual(status, "windows_bundle")
        for name in net.CA_ENV_VARS:
            self.assertEqual(os.environ[name], str(bundle))

    def test_non_windows_cert_error_is_unresolved_without_truststore(self) -> None:
        with mock.patch.dict(sys.modules, {"truststore": None}):
            status = net.configure_tls(probe=lambda: "cert_error", platform="linux")
        self.assertEqual(status, "unresolved")


class BuildBundleTests(unittest.TestCase):
    def test_bundle_contains_certifi_and_store_certs(self) -> None:
        def fake_enum(store: str) -> list:
            return [(SAMPLE_DER, "x509_asn", True), (b"ignored", "pkcs_7_asn", True)]

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "bundle.pem"
            net.build_windows_bundle(target, enum_certificates=fake_enum)
            text = target.read_text(encoding="ascii")
        certifi_count = Path(certifi.where()).read_text(encoding="ascii").count("BEGIN CERTIFICATE")
        # ROOT and CA both return the same cert; it is deduplicated to one extra entry.
        self.assertEqual(text.count("BEGIN CERTIFICATE"), certifi_count + 1)
        self.assertIn("Windows certificate store", text)

    def test_fresh_cache_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bundle.pem"
            target.write_text("cached", encoding="ascii")
            net.build_windows_bundle(target, enum_certificates=lambda store: [])
            self.assertEqual(target.read_text(encoding="ascii"), "cached")
            old = time.time() - net.BUNDLE_MAX_AGE_SECONDS - 10
            os.utime(target, (old, old))
            net.build_windows_bundle(target, enum_certificates=lambda store: [])
            self.assertNotEqual(target.read_text(encoding="ascii"), "cached")


if __name__ == "__main__":
    unittest.main()
