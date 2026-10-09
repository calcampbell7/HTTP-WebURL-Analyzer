import json
import ipaddress
import re
import socket
import ssl
import sys
from urllib.parse import urljoin, urlparse


ALLOWED_PORTS = {80, 443}
MAX_REDIRECTS = 5
MAX_HEADER_BYTES = 64 * 1024
SOCKET_TIMEOUT_SECONDS = 5


def main():
    try:
        output_json, line = parse_cli_args(sys.argv[1:])
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)

    try:
        result = analyze(line)
    except Exception as error:
        if output_json:
            print(json.dumps({"ok": False, "error": str(error)}))
        else:
            print("Unable to establish TCP Connection")
            print("Please ensure that Valid URI is provided")
            print(f"Error: {error}")
        sys.exit(1)

    if output_json:
        print(json.dumps({"ok": True, **result}))
        return

    print_terminal_output(line, result)


def parse_cli_args(args):
    if not args:
        raise ValueError("no input URI was provided")

    if args[0] == "--json":
        if len(args) < 2:
            raise ValueError("no input URI was provided")
        return True, args[1]

    return False, args[0]


def analyze(input_line):
    return _analyze_url(input_line, input_line, redirects_remaining=MAX_REDIRECTS)


def _analyze_url(input_line, original_input, redirects_remaining):
    scheme, hostname, port, filepath = parse_input(input_line)
    formatted_hostname = f"[{hostname}]" if ":" in hostname else hostname
    current_url = f"{scheme}://{formatted_hostname}:{port}{filepath}"
    http_only = scheme == "http"
    cert_verified = True

    if http_only:
        conn = http_connect(hostname, port)
        http2_supported = False
    else:
        try:
            conn, http2_supported = https_connect(hostname, port)
        except ssl.SSLCertVerificationError:
            conn, http2_supported = https_connect(hostname, port, verify_cert=False)
            cert_verified = False

    host_header = formatted_hostname
    request = (
        f"GET {filepath} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Connection: close\r\n\r\n"
    )

    response_headers, _ = send_http_req(conn, request)
    status_code = get_header_code(response_headers)

    if status_code in ("301", "302", "303", "307", "308"):
        if redirects_remaining == 0:
            raise ValueError("Too many redirects")
        redirect_target = get_new_inputline(response_headers, current_url)
        return _analyze_url(
            redirect_target,
            original_input,
            redirects_remaining=redirects_remaining - 1,
        )

    cookies = get_cookies(response_headers)

    return {
        "input": original_input,
        "resolvedUrl": current_url,
        "request": request,
        "headers": response_headers,
        "statusCode": status_code,
        "supportsHttp2": http2_supported,
        "cookies": cookies,
        "passwordProtected": status_code == "401",
        "tlsCertificateVerified": cert_verified,
        "transport": "http" if http_only else "https",
    }


def print_terminal_output(input_line, result):
    print(input_line)
    print(result["request"])
    print("---Request sent---")
    print()
    print("---Printing http response header---")
    print(result["headers"])
    print("---done printing http header---")
    print()
    print("---Now printing website characterisics---")
    print()
    print(f"1. Supports http2? : {'Yes' if result['supportsHttp2'] else 'No'}")
    print()
    print("2. Printing all cookies")
    print()

    if result["cookies"]:
        for cookie in result["cookies"]:
            cookie_parts = [f"Cookie name: {cookie['name']}"]
            if cookie["expires"]:
                cookie_parts.append(f"expires time: {cookie['expires']}")
            if cookie["domain"]:
                cookie_parts.append(f"domain name: {cookie['domain']}")
            print(", ".join(cookie_parts))
    else:
        print("No cookies found")

    print("Done Printing cookies")
    print()
    print(f"3. Password Protected?: {'Yes' if result['passwordProtected'] else 'No'}")
    print(f"4. TLS Certificate Verified?: {'Yes' if result['tlsCertificateVerified'] else 'No'}")


def http_connect(hostname, portnum):
    return connect_public_address(hostname, portnum)


def get_new_inputline(headers, current_url):
    for line in headers.splitlines():
        if line.lower().startswith("location:"):
            return urljoin(current_url, line.split(":", 1)[1].strip())
    raise ValueError("Redirect response did not include a Location header")


def get_header_code(header):
    first_line = header.splitlines()[0]
    code = re.search(r"(\d\d\d)", first_line)
    if code is None:
        raise ValueError("Unable to determine HTTP status code from response")
    return code.group(1)


def get_cookies(header):
    cookies = []
    for line in header.splitlines():
        if re.match(r"^(Set-Cookie:)", line):
            name_match = re.search(r"^Set-Cookie:\s*([^=;]+)", line)
            if name_match is None:
                continue
            expires_match = re.search(r"(expires=)([^;]+)", line, re.IGNORECASE)
            domain_match = re.search(r"(domain=)([^;]+)", line, re.IGNORECASE)
            cookies.append(
                {
                    "name": name_match.group(1),
                    "expires": expires_match.group(2) if expires_match else None,
                    "domain": domain_match.group(2) if domain_match else None,
                }
            )
    return cookies


def parse_input(line):
    if any(ord(character) < 32 or ord(character) == 127 for character in line):
        raise ValueError("URL contains invalid control characters")

    parsed = urlparse(line)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not allowed")

    hostname = parsed.hostname

    if hostname is None:
        raise ValueError("Unable to determine hostname from URI")

    filepath = parsed.path if parsed.path else "/"

    if parsed.query:
        filepath += f"?{parsed.query}"

    try:
        explicit_port = parsed.port
    except ValueError as error:
        raise ValueError("Invalid URL port") from error

    if explicit_port is not None:
        port = explicit_port
    elif scheme == "http":
        port = 80
    else:
        port = 443

    if port not in ALLOWED_PORTS:
        raise ValueError("Only ports 80 and 443 are allowed")

    return scheme, hostname, port, filepath


def resolve_public_addresses(hostname, port):
    try:
        address_info = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise ValueError("Unable to resolve hostname") from error

    if not address_info:
        raise ValueError("Unable to resolve hostname")

    public_addresses = []
    seen = set()
    for family, socktype, protocol, _, sockaddr in address_info:
        address = ipaddress.ip_address(sockaddr[0].split("%", 1)[0])
        if not address.is_global:
            raise ValueError("Local, private, and reserved addresses are not allowed")

        key = (family, sockaddr)
        if key not in seen:
            seen.add(key)
            public_addresses.append((family, socktype, protocol, sockaddr))

    return public_addresses


def connect_public_address(hostname, port, ssl_context=None):
    last_error = None
    for family, socktype, protocol, sockaddr in resolve_public_addresses(hostname, port):
        raw_socket = socket.socket(family, socktype, protocol)
        raw_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
        connection = raw_socket
        try:
            if ssl_context is not None:
                connection = ssl_context.wrap_socket(raw_socket, server_hostname=hostname)
            connection.connect(sockaddr)
            return connection
        except ssl.SSLCertVerificationError:
            connection.close()
            raise
        except (OSError, ssl.SSLError) as error:
            last_error = error
            connection.close()

    raise ConnectionError("Unable to connect to destination") from last_error


def https_connect(hostname, port_num, verify_cert=True):
    http2_supported = False
    context = ssl.create_default_context() if verify_cert else ssl._create_unverified_context()
    context.set_alpn_protocols(["h2", "http/1.1"])
    conn = connect_public_address(hostname, port_num, ssl_context=context)
    negotiated_protocol = conn.selected_alpn_protocol()

    if negotiated_protocol == "h2":
        conn.close()
        new_context = ssl.create_default_context() if verify_cert else ssl._create_unverified_context()
        new_context.set_alpn_protocols(["http/1.1"])
        new_conn = connect_public_address(hostname, port_num, ssl_context=new_context)
        http2_supported = True
        return new_conn, http2_supported

    return conn, http2_supported


def send_http_req(connection, request):
    try:
        connection.sendall(request.encode("utf-8"))
    except Exception as error:
        connection.close()
        raise RuntimeError(f"Unable to send http request: {error}") from error

    try:
        chunks = []
        total_bytes = 0
        raw_headers = None
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            total_bytes += len(chunk)
            combined = b"".join(chunks)
            header_end = combined.find(b"\r\n\r\n")
            if header_end != -1:
                raw_headers = combined[:header_end]
                break
            if total_bytes > MAX_HEADER_BYTES:
                raise ValueError("Response headers are too large")

        if raw_headers is None:
            raw_headers = b"".join(chunks)
        if len(raw_headers) > MAX_HEADER_BYTES:
            raise ValueError("Response headers are too large")
        headers = raw_headers.decode("utf-8", errors="replace")
    except Exception as error:
        connection.close()
        raise RuntimeError(f"Unable to receive http response: {error}") from error

    connection.close()

    return headers, None


if __name__ == "__main__":
    main()
