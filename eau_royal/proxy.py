"""Resolve the visitor address behind the bundled reverse proxy without trusting clients.

Only when the TCP peer (REMOTE_ADDR) belongs to ``TRUSTED_PROXY_NETWORKS`` is the
right-most ``X-Forwarded-For`` entry used: that entry is the one written by our own
proxy (Caddy replaces client-supplied values). Any other request keeps its peer
address, so a client cannot spoof its origin by sending the header directly.
"""

from ipaddress import ip_address, ip_network

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def parse_networks(values):
    try:
        return tuple(ip_network(value, strict=False) for value in values)
    except ValueError as exc:
        raise ImproperlyConfigured(f"Invalid TRUSTED_PROXY_NETWORKS entry: {exc}") from exc


def valid_ip(value):
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return None


class TrustedProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.networks = parse_networks(getattr(settings, "TRUSTED_PROXY_NETWORKS", ()))

    def __call__(self, request):
        if self.networks:
            peer = valid_ip(request.META.get("REMOTE_ADDR", ""))
            if peer and any(ip_address(peer) in network for network in self.networks):
                forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
                client = valid_ip(forwarded[-1]) if forwarded and forwarded[-1].strip() else None
                if client:
                    request.META["REMOTE_ADDR"] = client
        return self.get_response(request)
