"""mDNS/Zeroconf advertisement for the Servo Camera web service."""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import uuid
from dataclasses import dataclass, field
from typing import Iterable, Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf

_LOGGER = logging.getLogger(__name__)


def _iter_candidate_ips() -> Iterable[str]:
    """Yield potential IPv4 addresses for advertising."""

    def _valid(ip: str) -> bool:
        if not ip:
            return False
        if ip.startswith("127."):
            return False
        if ip in {"0.0.0.0", "255.255.255.255"}:
            return False
        return True

    # First try by checking outbound interfaces via common targets.
    for target in (("224.0.0.251", 5353), ("8.8.8.8", 80), ("1.1.1.1", 80)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(target)
                candidate = sock.getsockname()[0]
            if _valid(candidate):
                yield candidate
        except OSError:
            continue

    # Inspect hostname lookups for additional addresses.
    for resolver in (socket.gethostname, socket.getfqdn):
        try:
            _, _, addresses = socket.gethostbyname_ex(resolver())
        except OSError:
            continue
        for candidate in addresses:
            if _valid(candidate):
                yield candidate

    # Enumerate address info for any configured interfaces.
    try:
        infos = socket.getaddrinfo(None, 0, family=socket.AF_INET, type=socket.SOCK_DGRAM)
    except OSError:
        infos = []
    for info in infos:
        try:
            candidate = info[4][0]
        except (IndexError, TypeError):
            continue
        if _valid(candidate):
            yield candidate


def _detect_ip_address(configured_host: str | None) -> str:
    """Return the best IP address to advertise to the network."""

    if configured_host and configured_host not in {"0.0.0.0", "::"}:
        return configured_host

    for candidate in _iter_candidate_ips():
        _LOGGER.debug("Zeroconf candidate IP detected: %s", candidate)
        return candidate

    _LOGGER.warning(
        "Falling back to loopback address for Zeroconf advertisement; discovery may be limited"
    )
    return "127.0.0.1"


def _ip_to_bytes(ip: str) -> list[bytes]:
    """Convert an IP address to the packed format expected by Zeroconf."""
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return []

    return [ip_obj.packed]


@dataclass
class ServoCamZeroconf:
    """Manage Zeroconf advertisement for the Servo Camera service."""

    host: str
    port: int
    service_type: str = "_servo-cam._tcp.local."

    _zeroconf: Optional[Zeroconf] = field(init=False, default=None, repr=False)
    _service_info: Optional[ServiceInfo] = field(init=False, default=None, repr=False)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock, repr=False)

    def start(self) -> None:
        """Register the mDNS service on the local network."""
        with self._lock:
            if self._zeroconf is not None:
                return

            advertised_ip = _detect_ip_address(self.host)
            addresses = _ip_to_bytes(advertised_ip)
            if not addresses:
                raise RuntimeError("Unable to determine IP address for Zeroconf advertisement")

            hostname = socket.gethostname()
            unique_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"servo-cam-{hostname}-{self.port}")

            properties = {
                "uuid": str(unique_id).encode(),
                "name": hostname.encode(),
                "api_path": b"/healthz",
            }

            service_name = f"Servo Camera ({hostname}).{self.service_type}"

            self._zeroconf = Zeroconf(ip_version=IPVersion.All)
            self._service_info = ServiceInfo(
                type_=self.service_type,
                name=service_name,
                addresses=addresses,
                port=self.port,
                server=f"{hostname}.local.",
                properties=properties,
            )

            self._zeroconf.register_service(self._service_info)
            _LOGGER.info(
                "Servo Camera Zeroconf service advertised on %s:%s", advertised_ip, self.port
            )

    def stop(self) -> None:
        """Unregister the mDNS service."""
        with self._lock:
            if self._zeroconf and self._service_info:
                try:
                    self._zeroconf.unregister_service(self._service_info)
                finally:
                    self._zeroconf.close()
            self._zeroconf = None
            self._service_info = None
