import socket
import unittest
from unittest.mock import Mock, patch

from backend import Webtester


class ParseInputTests(unittest.TestCase):
    def test_accepts_explicit_http_and_https_urls(self):
        self.assertEqual(
            Webtester.parse_input("https://example.com/path?q=1#ignored"),
            ("https", "example.com", 443, "/path?q=1"),
        )
        self.assertEqual(
            Webtester.parse_input("http://example.com"),
            ("http", "example.com", 80, "/"),
        )

    def test_rejects_missing_or_unsupported_scheme(self):
        for url in ("example.com", "ftp://example.com", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Webtester.parse_input(url)

    def test_rejects_credentials_nonstandard_ports_and_control_characters(self):
        urls = (
            "https://user:password@example.com",
            "https://example.com:8443",
            "https://example.com/path\r\nInjected: value",
        )
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                Webtester.parse_input(url)


class AddressValidationTests(unittest.TestCase):
    @patch("backend.Webtester.socket.getaddrinfo")
    def test_rejects_nonpublic_addresses(self, getaddrinfo):
        for address in (
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "192.168.1.1",
            "::1",
            "fc00::1",
        ):
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
            getaddrinfo.return_value = [(family, socket.SOCK_STREAM, 6, "", sockaddr)]
            with self.subTest(address=address), self.assertRaises(ValueError):
                Webtester.resolve_public_addresses("example.com", 443)

    @patch("backend.Webtester.socket.getaddrinfo")
    def test_rejects_hostname_if_any_answer_is_private(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with self.assertRaises(ValueError):
            Webtester.resolve_public_addresses("example.com", 443)

    @patch("backend.Webtester.socket.socket")
    @patch("backend.Webtester.socket.getaddrinfo")
    def test_connects_to_validated_ip_not_hostname(self, getaddrinfo, socket_factory):
        destination = ("93.184.216.34", 443)
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", destination),
        ]
        connection = Mock()
        socket_factory.return_value = connection

        Webtester.connect_public_address("example.com", 443)

        connection.connect.assert_called_once_with(destination)
        connection.settimeout.assert_called_once_with(Webtester.SOCKET_TIMEOUT_SECONDS)


class RedirectTests(unittest.TestCase):
    @patch("backend.Webtester.send_http_req")
    @patch("backend.Webtester.http_connect")
    def test_stops_after_redirect_limit(self, http_connect, send_http_req):
        http_connect.return_value = Mock()
        send_http_req.return_value = (
            "HTTP/1.1 302 Found\r\nLocation: http://example.com/next",
            None,
        )

        with self.assertRaisesRegex(ValueError, "Too many redirects"):
            Webtester._analyze_url(
                "http://example.com",
                "http://example.com",
                redirects_remaining=0,
            )


if __name__ == "__main__":
    unittest.main()
