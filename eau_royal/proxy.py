"""Resolve the visitor address behind a reverse proxy without trusting clients.

Only when the TCP peer (REMOTE_ADDR) is a trusted proxy is the right-most
``X-Forwarded-For`` entry used: that entry is the one written by the proxy itself
(Caddy replaces client-supplied values). Any other request keeps its peer address,
so a client cannot spoof its origin by sending the header directly.

Trusted proxies are given as networks (``TRUSTED_PROXY_NETWORKS``, e.g. the fixed IP
of the bundled Caddy) and/or container names (``TRUSTED_PROXY_HOSTS``, e.g. a shared
Caddy owned by another Compose project whose IP may change when it is recreated).
Names are re-resolved at most every ``RESOLVE_TTL`` seconds; if resolution fails no
address is trusted, so the limiter falls back to the peer address (fail closed).
"""

import socket
import time
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


RESOLVE_TTL = 30


def parse_networks(values):
    try:
        return tuple(ip_network(value, strict=False) for value in values)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Invalid TRUSTED_PROXY_NETWORKS entry: {exc}") from exc


def parse_hosts(values):
    hosts = tuple(value.strip() for value in values if value.strip())
    for host in hosts:
        if "/" in host or any(char.isspace() for char in host):
            raise ImproperlyConfigured(f"Invalid TRUSTED_PROXY_HOSTS entry: {host!r}")
    return hosts


def valid_ip(value):
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return None


def resolve(hosts):
    addresses = set()
    for host in hosts:
        try:
            for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP):
                addresses.add(ip_address(info[4][0]))
        except (OSError, ValueError):
            continue
    return frozenset(addresses)


class TrustedProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.networks = parse_networks(getattr(settings, "TRUSTED_PROXY_NETWORKS", ()))
        self.hosts = parse_hosts(getattr(settings, "TRUSTED_PROXY_HOSTS", ()))
        self._resolved = frozenset()
        self._resolved_at = None

    def host_addresses(self):
        now = time.monotonic()
        if self._resolved_at is None or now - self._resolved_at >= RESOLVE_TTL:
            self._resolved = resolve(self.hosts)
            self._resolved_at = now
        return self._resolved

    def is_trusted(self, peer):
        address = ip_address(peer)
        if any(address in network for network in self.networks):
            return True
        return bool(self.hosts) and address in self.host_addresses()

    def __call__(self, request):
        if self.networks or self.hosts:
            peer = valid_ip(request.META.get("REMOTE_ADDR", ""))
            if peer and self.is_trusted(peer):
                forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
                client = valid_ip(forwarded[-1]) if forwarded and forwarded[-1].strip() else None
                if client:
                    request.META["REMOTE_ADDR"] = client
        return self.get_response(request)
