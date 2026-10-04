"""Client address for rate limiting, safe against forged ``X-Forwarded-For``."""

from __future__ import annotations

import ipaddress

from starlette.types import Scope

UNKNOWN_CLIENT = "unknown"
IPV6_PREFIX = 64
# A typical site allocation (one home or office); see subnet_key.
IPV6_SITE_PREFIX = 48


def client_ip(scope: Scope, trusted_proxy_hops: int) -> str:
    """Return the address to rate-limit on.

    With ``trusted_proxy_hops == 0`` the socket peer is used. Behind N trusted
    proxies (Render: 1), each proxy appends the address it saw, so the Nth entry
    from the right is the real client; entries further left are client-supplied
    and ignored.
    """
    if trusted_proxy_hops > 0:
        forwarded = _header(scope, b"x-forwarded-for")
        hops = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(hops) >= trusted_proxy_hops:
            return hops[-trusted_proxy_hops]
    client = scope.get("client")
    return client[0] if client else UNKNOWN_CLIENT


def rate_limit_key(address: str) -> str:
    """One key per IPv4 address, one per IPv6 /64 (a single host usually owns the whole /64)."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/{IPV6_PREFIX}", strict=False))
    return str(ip)


def subnet_key(address: str) -> str | None:
    """The IPv6 /48 an address belongs to, or ``None`` for IPv4 and unparsable addresses.

    NEW-4: a client holding a /48 owns 65,536 /64 keys; a second, looser limit per /48 stops
    it from rotating past the per-/64 limit or filling the key table.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if ip.version != 6:
        return None
    return str(ipaddress.ip_network(f"{ip}/{IPV6_SITE_PREFIX}", strict=False))


def _header(scope: Scope, name: bytes) -> str:
    """Join every occurrence of a header, as proxies may send it more than once."""
    values = [value.decode("latin-1") for key, value in scope.get("headers", []) if key == name]
    return ",".join(values)
