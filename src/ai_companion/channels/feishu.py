"""
Feishu/Lark channel.
Supports:
- Long connection mode (no public IP needed - recommended, matches your settings)
Uses official lark-oapi SDK for reliable connection.
"""

import asyncio
import json
import time
import threading
from typing import AsyncGenerator, Optional, Any, Dict
from dataclasses import dataclass
import httpx
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from ai_companion.types.message import InboundMessage, OutboundMessage
from ai_companion.config.schema import AppConfig
from ai_companion.logging.logger import get_logger
from .base import Channel

logger = get_logger(__name__)


@dataclass
class FeishuToken:
    """Feishu access token with expiration."""
    token: str
    expires_at: int


class FeishuClient:
    """Feishu API client."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[FeishuToken] = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if expired."""
        if self._token and self._token.expires_at > time.time() + 60:
            return self._token.token

        if not self.app_id or not self.app_secret:
            logger.error("Feishu app_id and app_secret not configured")
            return None

        try:
            response = await self._client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            data = response.json()
            if data.get("code") == 0:
                token = data["tenant_access_token"]
                expires_at = int(time.time()) + data["expire"] - 300
                self._token = FeishuToken(token=token, expires_at=expires_at)
                return token
            else:
                logger.error(f"Failed to get Feishu token: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting Feishu token: {e}")
            return None

    async def send_text(self, chat_id: str, text: str) -> bool:
        """Send text message to a chat.
        Split by newlines into multiple messages.
        """
        token = await self.get_access_token()
        if not token:
            return False

        # Log raw text received from LLM (repr shows invisible chars)
        logger.info(f"[FEISHU SEND] Raw from LLM: {repr(text)}")

        # Split by newlines into multiple messages
        # Strip trailing backslash from each line (for backward compatibility with old format)
        messages = []
        for msg in text.split('\n'):
            msg = msg.strip()
            if not msg:
                continue
            # Remove trailing backslash if present (from old formatting habit)
            if msg.endswith('\\'):
                msg = msg[:-1].rstrip()
            if msg:
                messages.append(msg)

        # If no splitting needed, just send as-is
        if not messages:
            messages = [text]

        logger.info(f"[FEISHU SEND] Split into {len(messages)} message(s):")
        for idx, msg in enumerate(messages):
            logger.info(f"[FEISHU SEND] Message {idx+1}: {repr(msg)}")

        all_success = True
        for idx, msg in enumerate(messages):
            try:
                # Feishu requires content field to be a JSON-encoded string
                # So we dump {"text": msg} once to get the JSON string
                content = json.dumps({"text": msg}, ensure_ascii=False)
                logger.info(f"[FEISHU SEND] Message {idx+1} final JSON: {repr(content)}")
                response = await self._client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"receive_id_type": "chat_id"},
                    json={
                        "receive_id": chat_id,
                        "msg_type": "text",
                        "content": content
                    }
                )
                data = response.json()
                if data.get("code") != 0:
                    logger.error(f"Failed to send Feishu message: {data}")
                    all_success = False
            except Exception as e:
                logger.error(f"Error sending Feishu message: {e}")
                all_success = False

        return all_success

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class FeishuChannel(Channel):
    """Feishu/Lark channel using official lark-oapi long connection (no public IP needed).

    Matches your Feishu settings: "Use long connection to receive events"
    """

    def __init__(self, config: AppConfig, host: str = "0.0.0.0", port: int = 8080):
        self.config = config
        self._channel_id = "feishu"
        self._running = False
        self._client = FeishuClient(config.feishu_app_id, config.feishu_app_secret)
        self._queue: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=100)
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_client: Optional[lark.ws.Client] = None
        # Capture the main event loop reference on init
        self._main_loop = asyncio.get_event_loop()

    @property
    def channel_id(self) -> str:
        return self._channel_id

    def _handle_message(self, data: P2ImMessageReceiveV1) -> None:
        """Handle incoming message receive event from official SDK."""
        try:
            message = data.event.message
            if message.message_type != "text":
                logger.debug(f"Ignoring non-text message type: {message.message_type}")
                return

            content = json.loads(message.content)
            text = content.get("text", "").strip()
            if not text:
                return

            chat_id = message.chat_id
            message_id = message.message_id
            sender_id = data.event.sender.sender_id

            inbound = InboundMessage(
                channel_id="feishu",
                peer_id=chat_id,
                content=text,
                message_id=message_id,
                timestamp=int(time.time()),
                metadata={
                    "sender_id": sender_id,
                    "raw_event": data
                }
            )

            # We need to use call_soon_threadsafe since this callback
            # is executed in a background thread managed by lark-sdk
            # Use the captured main loop from __init__ which runs the receive loop
            self._main_loop.call_soon_threadsafe(lambda: self._queue.put_nowait(inbound))
            logger.info(f"Queued Feishu message from {chat_id}: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error processing Feishu message: {e}")
            import traceback
            traceback.print_exc()

    def _ws_run_thread(self) -> None:
        """Background thread to run official lark websocket client."""
        # Need verification token and encrypt key from Feishu app settings
        # Get these from: Feishu Open Platform -> Your App -> Development -> Events & Callbacks -> Encryption
        verification_token = getattr(self.config, 'feishu_verification_token', '')
        encrypt_key = getattr(self.config, 'feishu_encrypt_key', '')

        # Create event dispatcher
        event_handler = (
            lark.EventDispatcherHandler.builder(verification_token, encrypt_key)
            .register_p2_im_message_receive_v1(self._handle_message)
            .build()
        )

        # Create websocket client
        self._ws_client = lark.ws.Client(
            self.config.feishu_app_id,
            self.config.feishu_app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("Feishu long connection client started")
        # This blocks until stopped
        self._ws_client.start()
        logger.info("Feishu long connection client exited")

    async def start(self) -> None:
        """Start Feishu channel with official long connection (no public IP needed)."""
        self._running = True
        logger.info("Starting Feishu channel with long connection (official SDK)")
        logger.info("✅ No public domain/IP required - connecting outbound to Feishu")

        # Start websocket client in background thread
        # Official lark-oapi ws client runs synchronously
        self._ws_thread = threading.Thread(
            target=self._ws_run_thread,
            daemon=True
        )
        self._ws_thread.start()
        logger.info("Feishu long connection started in background thread")

    async def stop(self) -> None:
        """Stop the channel."""
        self._running = False
        if self._ws_client:
            # Stop the websocket client - check if method exists (different versions have different names)
            if hasattr(self._ws_client, 'stop'):
                self._ws_client.stop()
            elif hasattr(self._ws_client, 'close'):
                self._ws_client.close()
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5.0)
        await self._client.aclose()

    async def receive(self) -> AsyncGenerator[InboundMessage, None]:
        """Yield incoming messages from the queue."""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                yield message
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue

    async def send(self, message: OutboundMessage) -> bool:
        """Send a message to Feishu."""
        target_peer = message.target_peer
        return await self._client.send_text(target_peer, message.content)
