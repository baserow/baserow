# SSRF Protection

## What is SSRF?

Server-Side Request Forgery (SSRF) is a vulnerability where an attacker tricks a
server into making HTTP requests to unintended destinations. In Baserow's case, users
can configure webhooks, integrations, data syncs, and file imports that cause the
backend to make outbound HTTP requests. Without protection, a malicious user could
target:

- **Internal services** (e.g., `http://127.0.0.1:8080/admin`) to access admin panels
  or APIs not exposed to the internet.
- **Cloud metadata endpoints** (e.g., `http://169.254.169.254/`) to steal cloud
  credentials on AWS/GCP/Azure.
- **Private network hosts** (e.g., `http://192.168.1.1/`) to scan or exploit internal
  infrastructure.

## How Baserow protects against SSRF

Baserow has a custom SSRF protection module at `baserow.core.ssrf` that validates
resolved IP addresses before any outbound HTTP connection is established.

### Architecture

The module consists of four components:

```
baserow/core/ssrf/
    __init__.py       # Public API: ssrf_safe_request(), validate_url()
    exceptions.py     # InvalidSSRFAddress exception
    validator.py      # SSRFValidator: IP and hostname validation rules
    adapter.py        # SSRFSafeAdapter: requests HTTPAdapter with validation
```

#### SSRFValidator

The core validation engine. When given a hostname and port, it:

1. **Checks the hostname** against a configurable regex blacklist (e.g., block
   `*.internal.company.com`).
2. **Resolves DNS** via `socket.getaddrinfo()` to get the actual IP address(es).
3. **Validates each IP** against:
   - User-configured IP whitelist (explicit allow, highest priority)
   - User-configured IP blacklist (explicit deny)
   - Built-in rules: blocks all private (`is_private`) and non-globally-routable
     (`not is_global`) addresses

The built-in rules block:

| Range | Description |
|-------|-------------|
| `127.0.0.0/8` | Loopback |
| `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` | RFC 1918 private networks |
| `169.254.0.0/16` | Link-local (includes cloud metadata) |
| `100.64.0.0/10` | Carrier-Grade NAT (CGNAT) |
| `192.88.99.0/24` | 6to4 relay anycast |
| `0.0.0.0/8` | Unspecified |
| `240.0.0.0/4` | Reserved |
| `255.255.255.255` | Broadcast |
| `::1`, `fe80::/10`, `fc00::/7` | IPv6 loopback, link-local, unique local |

IPv4-mapped IPv6 addresses (e.g., `::ffff:127.0.0.1`) are automatically unwrapped
and checked as their inner IPv4 address.

#### SSRFSafeAdapter

A `requests.adapters.HTTPAdapter` subclass that hooks into the connection setup
process. It overrides `build_connection_pool_key_attributes()` (available since
`requests >= 2.32.2`) to:

1. Resolve the hostname and validate the IP via `SSRFValidator`.
2. Rewrite the connection target from hostname to the resolved IP, preventing
   TOCTOU (time-of-check-time-of-use) races where DNS could resolve differently
   between validation and connection.
3. Preserve the original hostname in the `Host` header and TLS SNI/certificate
   verification, so HTTPS works correctly even though the TCP connection goes to
   the resolved IP.

This approach uses the official `requests` adapter API instead of patching urllib3
internals, making it stable across dependency upgrades.

#### Public API

**`ssrf_safe_request`**

Module-level client instance with convenience methods (`.get()`, `.post()`,
`.request()`, etc.) that mirror the `requests` library API. Each call creates a
session with `SSRFSafeAdapter` mounted for both `http://` and `https://`.

```python
from baserow.core.ssrf import ssrf_safe_request

# Convenience methods
response = ssrf_safe_request.get("https://example.com/api", timeout=10)
response = ssrf_safe_request.post("https://example.com/api", json={"key": "value"})

# Generic request method (used by webhooks with configurable validators)
response = ssrf_safe_request.request("POST", url, validator=custom_validator, json=data)
```

**`validate_url(hostname, port, validator=None)`**

Pre-flight URL validation without making an HTTP request. Used by webhook URL
validation to check addresses at save time.

```python
from baserow.core.ssrf import validate_url, SSRFValidator

validator = SSRFValidator(
    ip_whitelist=[ip_network("10.0.0.5/32")],
    hostname_blacklist=[re.compile(r"evil\.com")],
)
validate_url("example.com", 443, validator=validator)
```

## Configuration

SSRF protection is controlled by these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS` | Disable SSRF protection for webhooks entirely | `False` |
| `BASEROW_INTEGRATIONS_ALLOW_PRIVATE_ADDRESS` | Disable SSRF protection for integrations | `False` |
| `BASEROW_WEBHOOKS_IP_BLACKLIST` | Comma-separated CIDR ranges to block (e.g., `1.2.3.0/24,5.6.7.8/32`) | Empty |
| `BASEROW_WEBHOOKS_IP_WHITELIST` | Comma-separated CIDR ranges to allow (overrides blacklist and defaults) | Empty |
| `BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST` | Comma-separated regex patterns to block hostnames | Empty |
| `BASEROW_WEBHOOKS_URL_CHECK_TIMEOUT_SECS` | Timeout for pre-flight URL validation | `10` |

**Note:** The IP whitelist takes precedence over the blacklist. If an IP matches
both, it is allowed. This lets administrators whitelist specific internal services
that webhooks need to reach.

**Note:** The `ALLOW_PRIVATE_ADDRESS` flags completely bypass SSRF protection. They
should only be set in development or trusted environments.

## Where SSRF protection is applied

| Feature | Module | Function |
|---------|--------|----------|
| Webhooks (request) | `webhooks/validators.py` | `get_webhook_request_function()` |
| Webhooks (URL validation) | `webhooks/validators.py` | `url_validator()` |
| HTTP integrations | `integrations/utils.py` | `get_http_request_function()` |
| Slack integration | `integrations/slack/service_types.py` | Via `get_http_request_function()` |
| User file upload by URL | `core/user_files/handler.py` | Direct `ssrf_safe_request()` call |
| iCal data sync | `database/data_sync/ical_data_sync_type.py` | Direct `ssrf_safe_request()` call |
| Jira data sync | `enterprise/.../jira_issues_data_sync.py` | Direct `ssrf_safe_request()` call |

## Testing

### Running SSRF tests

```bash
# Unit tests for the SSRF module itself
pytest backend/tests/baserow/core/ssrf/

# Webhook validator tests (integration with Django settings)
pytest backend/tests/baserow/contrib/database/webhooks/test_webhook_validators.py

# HTTP request service type tests
pytest backend/tests/baserow/contrib/integrations/core/test_core_http_request_service_type.py
```

### Writing tests that involve SSRF protection

When testing code that makes outbound HTTP requests through SSRF protection, you
need to mock DNS resolution because `httpretty` doesn't properly stub
`socket.getaddrinfo`. Use the `stub_getaddrinfo` helper:

```python
from unittest.mock import patch
from baserow.test_utils.helpers import stub_getaddrinfo

@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_my_feature(mock_getaddrinfo):
    # stub_getaddrinfo resolves IP strings to themselves,
    # and hostnames to 1.1.1.1 (a public IP that passes validation)
    ...
```

To mock the HTTP request itself (without actually connecting), patch the
`ssrf_safe_request` object at the point of use:

```python
from unittest.mock import patch, Mock

# Patch at the import location, not at the definition site
with patch("mymodule.ssrf_safe_request") as mock_client:
    mock_client.get.return_value = Mock(status_code=200, json=lambda: {"ok": True})
    # your code that calls ssrf_safe_request.get(...)
```

## History

Baserow used the `advocate` library for SSRF protection for a long time. When
updating dependencies, we were forced to replace it because it was no longer
maintained and its pinned transitive dependencies couldn't be upgraded.

We took inspiration from advocate's validation approach and built a focused
in-house module that covers exactly what Baserow needs:

- Uses the standard `requests` adapter API (`build_connection_pool_key_attributes`).
- Has zero additional dependencies (only `requests` + Python stdlib).
- Supports configurable IP whitelist/blacklist and hostname regex patterns.
- Is ~200 lines of focused code covering Baserow's specific requirements.
