"""Best-effort LAN broadcast discovery.

Used to re-locate a fan by its stable miIO device ID after its IP address has
changed (e.g. a DHCP lease renewal). This mirrors the same handshake
`miiocli discover` uses (a 32-byte "hello" packet broadcast on port 54321),
but collects the replies instead of only logging them.
"""

from __future__ import annotations

import logging
import socket

_LOGGER = logging.getLogger(__name__)

_HELLO = bytes.fromhex(
    "21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)
_MIIO_PORT = 54321


def broadcast_discover_device_ids(timeout: float = 3.0) -> dict[int, str]:
    """Broadcast a miIO handshake and collect {device_id: ip} for replies.

    This is blocking socket I/O - callers must run it via
    `hass.async_add_executor_job`. Best-effort: returns an empty dict rather
    than raising if the network is unavailable or python-miio's wire format
    ever changes underneath us, since losing auto-heal shouldn't take the
    integration down with it.
    """
    try:
        from miio.protocol import Message  # noqa: PLC0415
    except ImportError:
        _LOGGER.debug("miio.protocol.Message is unavailable, cannot auto-heal IPs")
        return {}

    found: dict[int, str] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as ex:
        _LOGGER.debug("Could not open a socket for discovery: %s", ex)
        return found

    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        for _ in range(3):
            sock.sendto(_HELLO, ("<broadcast>", _MIIO_PORT))

        while True:
            try:
                data, (ip, _port) = sock.recvfrom(1024)
            except TimeoutError:
                break
            except OSError as ex:
                _LOGGER.debug("Error while reading a discovery reply: %s", ex)
                continue

            try:
                message = Message.parse(data)
                device_id = int.from_bytes(message.header.value.device_id, "big")
            except Exception as ex:
                _LOGGER.debug(
                    "Ignoring a malformed discovery reply from %s: %s", ip, ex
                )
                continue

            found[device_id] = ip
    finally:
        sock.close()

    return found
