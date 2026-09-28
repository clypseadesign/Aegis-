"""Outbound network policy and SSRF protection for AegisAI.

User-configured target endpoints are untrusted input. Before any outbound
target connection is established, the endpoint is parsed, its scheme is
validated, embedded credentials are rejected, the hostname is resolved, and
every resolved address is checked against an allow/deny policy. Model adapters
disable automatic redirects so policy cannot be bypassed by redirection.
"""

import ipaddress
import socket
from fnmatch import fnmatch
from urllib.parse import urlsplit

from app.core.config import get_settings


class NetworkPolicyError(ValueError):
    """Raised when a target endpoint violates outbound network policy."""


_LINK_LOCAL_CIDR = ipaddress.ip_network("169.254.0.0/16")
_LOOPBACK_CIDR = ipaddress.ip_network("127.0.0.0/8")
_PRIVATE_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]
_METADATA_HOSTS = {"metadata.google.internal", "169.254.169.254"}


def _is_restricted_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return True
    if ip.version == 4:
        if ip in _LINK_LOCAL_CIDR:
            return True
        return any(ip in cidr for cidr in _PRIVATE_CIDRS)
    if ip.version == 6:
        if ip == ipaddress.ip_address("::1"):
            return True
        return ip.is_link_local or ip.is_private
    return True


def _resolved_addresses(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise NetworkPolicyError(f"target hostname could not be resolved: {hostname}") from exc
    resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address not in resolved:
            resolved.append(address)
    return resolved


def validate_target_endpoint(
    endpoint: str,
    *,
    allow_local: bool | None = None,
    allowed_hosts: list[str] | None = None,
) -> str:
    """Validate a user-configured target endpoint against outbound policy.

    Returns the validated endpoint URL. Raises NetworkPolicyError when the
    endpoint violates scheme, credential, host, or address policy.
    """

    parsed = urlsplit(endpoint)

    if parsed.scheme not in {"http", "https"}:
        raise NetworkPolicyError("target endpoint must use an http or https scheme")
    if not parsed.hostname:
        raise NetworkPolicyError("target endpoint must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise NetworkPolicyError("target endpoint must not contain credentials")

    hostname = parsed.hostname

    if hostname.lower() in _METADATA_HOSTS:
        raise NetworkPolicyError("cloud metadata endpoints are not permitted")

    if allowed_hosts and any(fnmatch(hostname, pattern) for pattern in allowed_hosts):
        return endpoint

    if allow_local is None:
        allow_local = get_settings().allow_local_targets

    if _is_ip_literal(hostname):
        candidate = ipaddress.ip_address(hostname)
        if _is_restricted_address(candidate) and not allow_local:
            raise NetworkPolicyError("local and private target addresses are not permitted")
        return endpoint

    for ip in _resolved_addresses(hostname):
        if _is_restricted_address(ip) and not allow_local:
            raise NetworkPolicyError(f"resolved target address {ip} is not permitted")

    return endpoint


def _is_ip_literal(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True
