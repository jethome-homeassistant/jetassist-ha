"""WebSocket tunnel client for JetAssist.

Runs inside HA integration, maintains a persistent WebSocket
connection to the tunnel server. Multiplexes incoming HTTP
connections from the server to localhost:8123 (HA).
"""

from __future__ import annotations

import asyncio
import logging
import struct
from enum import IntEnum

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Protocol constants (must match services/tunnel/protocol.py)
HEADER_SIZE = 22
HEADER_FORMAT = "!16sBIB"


class Flag(IntEnum):
    """Multiplexer frame flags."""

    NEW = 0x01
    DATA = 0x02
    CLOSE = 0x04
    PING = 0x08
    PONG = 0x09
    PAUSE = 0x16
    RESUME = 0x32


class TunnelClient:
    """WebSocket tunnel client running inside HA integration.

    Maintains a persistent connection to the tunnel server.
    Opens local TCP connections to HA for each incoming channel.
    """

    def __init__(
        self,
        server_url: str,
        token: str,
        local_port: int = 8123,
        local_host: str = "127.0.0.1",
    ) -> None:
        self.server_url = server_url
        self.token = token
        self.local_host = local_host
        self.local_port = local_port
        self._channels: dict[bytes, _ChannelHandler] = {}
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._reconnect_delay = 1.0
        self._running = False
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def connect(self) -> None:
        """Start the persistent connection loop."""
        self._running = True
        while self._running:
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.warning(
                    "Tunnel connection error: %s, reconnecting in %.0fs",
                    exc,
                    self._reconnect_delay,
                )
            if self._running:
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60.0)

    async def _connect_once(self) -> None:
        """Establish a single WebSocket connection."""
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(
                self.server_url,
                heartbeat=30,
            )
            # Authenticate: send JWT as first message
            await self._ws.send_str(self.token)

            self._reconnect_delay = 1.0
            _LOGGER.info("Tunnel connected to %s", self.server_url)

            # Main message loop
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await self._handle_frame(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", self._ws.exception())
                    break
        finally:
            # Cleanup channels
            for handler in list(self._channels.values()):
                handler.close()
            self._channels.clear()

            if self._ws and not self._ws.closed:
                await self._ws.close()
            if self._session and not self._session.closed:
                await self._session.close()
            self._ws = None
            self._session = None

    async def _handle_frame(self, data: bytes) -> None:
        """Parse and handle an incoming binary frame."""
        if len(data) < HEADER_SIZE:
            return

        channel_id, flag_val, size, extra = struct.unpack(
            HEADER_FORMAT, data[:HEADER_SIZE]
        )
        payload = data[HEADER_SIZE : HEADER_SIZE + size]

        try:
            flag = Flag(flag_val)
        except ValueError:
            _LOGGER.warning("Unknown flag: 0x%02x", flag_val)
            return

        if flag == Flag.PING:
            await self._send_pong()
            return

        if flag == Flag.PONG:
            return

        if flag == Flag.NEW:
            await self._open_channel(channel_id, payload)
        elif flag == Flag.DATA:
            handler = self._channels.get(channel_id)
            if handler:
                handler.feed_data(payload)
        elif flag == Flag.CLOSE:
            handler = self._channels.pop(channel_id, None)
            if handler:
                handler.close()
        elif flag == Flag.PAUSE:
            handler = self._channels.get(channel_id)
            if handler:
                handler.pause()
        elif flag == Flag.RESUME:
            handler = self._channels.get(channel_id)
            if handler:
                handler.resume()

    async def _open_channel(self, channel_id: bytes, payload: bytes) -> None:
        """Open a new local TCP connection for a channel."""
        try:
            reader, writer = await asyncio.open_connection(
                self.local_host, self.local_port
            )
        except OSError as exc:
            _LOGGER.error(
                "Cannot connect to local HA at %s:%s: %s",
                self.local_host,
                self.local_port,
                exc,
            )
            await self._send_close(channel_id)
            return

        handler = _ChannelHandler(channel_id, reader, writer, self)
        self._channels[channel_id] = handler
        asyncio.create_task(handler.read_from_local())

    async def _send_frame(self, channel_id: bytes, flag: Flag, payload: bytes = b"") -> None:
        """Send a frame to the tunnel server."""
        if self._ws is None or self._ws.closed:
            return
        header = struct.pack(HEADER_FORMAT, channel_id, flag, len(payload), 0)
        await self._ws.send_bytes(header + payload)

    async def _send_close(self, channel_id: bytes) -> None:
        """Send a CLOSE frame."""
        await self._send_frame(channel_id, Flag.CLOSE)

    async def _send_pong(self) -> None:
        """Send a PONG frame."""
        await self._send_frame(b"\x00" * 16, Flag.PONG)

    async def stop(self) -> None:
        """Stop the tunnel client."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        for handler in list(self._channels.values()):
            handler.close()
        self._channels.clear()


class _ChannelHandler:
    """Handles a single channel: bridges local TCP to tunnel WebSocket."""

    def __init__(
        self,
        channel_id: bytes,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client: TunnelClient,
    ) -> None:
        self.channel_id = channel_id
        self._reader = reader
        self._writer = writer
        self._client = client
        self._closed = False
        self._paused = False

    def feed_data(self, data: bytes) -> None:
        """Write data from tunnel to local HA connection."""
        if self._closed:
            return
        self._writer.write(data)

    async def read_from_local(self) -> None:
        """Read data from local HA and send to tunnel."""
        try:
            while not self._closed:
                data = await self._reader.read(4096)
                if not data:
                    break
                await self._client._send_frame(
                    self.channel_id, Flag.DATA, data
                )
        except (OSError, asyncio.CancelledError):
            pass
        finally:
            if not self._closed:
                await self._client._send_close(self.channel_id)
                self._client._channels.pop(self.channel_id, None)
            self.close()

    def pause(self) -> None:
        """Pause reading from local (flow control)."""
        self._paused = True

    def resume(self) -> None:
        """Resume reading from local."""
        self._paused = False

    def close(self) -> None:
        """Close the local connection."""
        if self._closed:
            return
        self._closed = True
        if not self._writer.is_closing():
            self._writer.close()
