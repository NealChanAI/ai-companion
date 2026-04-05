"""
HTTP webhook server for Feishu channel.
"""

import asyncio
import json
import time
import uuid
from typing import Optional
from aiohttp import web
import asyncio
from ai_companion.types.message import InboundMessage
from ai_companion.logging.logger import get_logger

logger = get_logger(__name__)


class FeishuWebhookServer:
    """HTTP webhook server that receives Feishu events and puts them in a queue."""

    def __init__(
        self,
        host: str,
        port: int,
        verification_token: Optional[str],
        queue: asyncio.Queue
    ):
        self.host = host
        self.port = port
        self.verification_token = verification_token
        self.queue = queue
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._running = False

    async def handle_challenge(self, request: web.Request) -> web.Response:
        """Handle URL verification challenge."""
        try:
            body = await request.json()
            challenge = body.get("challenge")
            return web.Response(
                text=json.dumps({"challenge": challenge}),
                content_type="application/json"
            )
        except Exception as e:
            logger.error(f"Error handling challenge: {e}")
            return web.Response(status=400, text="Bad request")

    async def handle_event_callback(self, request: web.Request) -> web.Response:
        """Handle incoming event callback."""
        try:
            body = await request.json()

            # Verify token if configured
            if self.verification_token:
                token = body.get("token")
                if token != self.verification_token:
                    return web.Response(status=403, text="Invalid token")

            event = body.get("event", {})
            message = event.get("message", {})

            # Only process text messages
            if message.get("msg_type") != "text":
                return web.Response(text="ok", content_type="text/plain")

            content = message.get("content", "").strip()
            if not content:
                return web.Response(text="ok", content_type="text/plain")

            # Get chat ID (where to send response back)
            if "chat_id" in event:
                chat_id = event["chat_id"]
            elif "chat" in event:
                chat_id = event["chat"]["chat_id"]
            else:
                # Can't respond without chat ID
                return web.Response(text="ok", content_type="text/plain")

            # Get sender ID
            sender = event.get("sender", {})
            sender_id = sender.get("sender_id", "unknown")
            message_id = message.get("message_id", str(uuid.uuid4()))

            # Create inbound message and put in queue
            inbound = InboundMessage(
                channel_id="feishu",
                peer_id=chat_id,  # Use chat_id as peer_id because we respond to this chat
                content=content,
                message_id=message_id,
                timestamp=int(time.time()),
                metadata={
                    "sender_id": sender_id,
                    "raw_event": event
                }
            )

            # Put in queue (non-blocking, drop if queue is full)
            try:
                self.queue.put_nowait(inbound)
                logger.info(f"Queued Feishu message from {chat_id}: {content[:50]}...")
            except asyncio.QueueFull:
                logger.warning("Feishu message queue full, dropping message")
                return web.Response(status=503, text="Queue full")

            return web.Response(text="ok", content_type="text/plain")

        except Exception as e:
            logger.error(f"Error processing Feishu event: {e}")
            return web.Response(status=500, text="Internal error")

    async def health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.Response(text="ok", content_type="text/plain")

    def _create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()
        app.add_routes([
            web.get("/health", self.health),
            web.post("/webhook/feishu", self.handle_event_callback),
            web.post("/webhook/feishu/challenge", self.handle_challenge),
        ])
        return app

    async def start(self) -> None:
        """Start the webhook server."""
        self._running = True
        app = self._create_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"Feishu webhook server started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the webhook server."""
        self._running = False
        if self._runner:
            await self._runner.cleanup()
        logger.info("Feishu webhook server stopped")
