import json
import re
import socket
import ssl
import sys
from urllib.parse import urljoin, urlparse


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
    return _analyze_url(input_line, input_line)


def _analyze_url(input_line, original_input):
    scheme, hostname, port, filepath = parse_input(input_line)
    current_url = f"{scheme}://{hostname}:{port}{filepath}"
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

    host_header = hostname if port in (80, 443) else f"{hostname}:{port}"
    request = (
        f"GET {filepath} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Connection: close\r\n\r\n"
    )

    response_headers, _ = send_http_req(conn, request)
    status_code = get_header_code(response_headers)

    if status_code in ("301", "302"):
        redirect_target = get_new_inputline(response_headers, current_url)
        return _analyze_url(redirect_target, original_input)

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
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostname, portnum))
    return sock


def get_new_inputline(headers, current_url):
    for line in headers.splitlines():
        if re.match(r"(Location: )(.*)", line):
            new = re.match(r"(Location: )(.*)", line)
            return urljoin(current_url, new.group(2))
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
    if not re.match(r"^(http|https)\:\/\/", line):
        line = f"https://{line}"

    parsed = urlparse(line)
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    hostname = parsed.hostname

    if hostname is None:
        raise ValueError("Unable to determine hostname from URI")

    filepath = parsed.path if parsed.path else "/"

    if parsed.query:
        filepath += f"?{parsed.query}"

    if parsed.fragment:
        filepath += f"#{parsed.fragment}"

    if parsed.port is not None:
        port = parsed.port
    elif scheme == "http":
        port = 80
    else:
        port = 443

    return scheme, hostname, port, filepath


def https_connect(hostname, port_num, verify_cert=True):
    http2_supported = False
    context = ssl.create_default_context() if verify_cert else ssl._create_unverified_context()
    context.set_alpn_protocols(["h2", "http/1.1"])
    conn = context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=hostname)
    conn.connect((hostname, port_num))
    negotiated_protocol = conn.selected_alpn_protocol()

    if negotiated_protocol == "h2":
        conn.close()
        new_context = ssl.create_default_context() if verify_cert else ssl._create_unverified_context()
        new_context.set_alpn_protocols(["http/1.1"])
        new_conn = new_context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=hostname)
        new_conn.connect((hostname, port_num))
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
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
    except Exception as error:
        connection.close()
        raise RuntimeError(f"Unable to receive http response: {error}") from error

    connection.close()

    try:
        headers, body = raw.split("\r\n\r\n", 1)
    except ValueError:
        headers = raw
        body = None

    return headers, body


if __name__ == "__main__":
    main()
