"""Channel & Voice Gateway — normalizes inbound/outbound messages by channel.

Voice traffic is transcribed on intake and synthesized on render; text channels
(SMS, portal chat) pass their payloads through unchanged.
"""
from __future__ import annotations

from ..application.ports import SpeechToTextPort, TextToSpeechPort
from ..domain.model import Channel, Language


class ChannelGateway:
    """Adapts channel payloads to/from text using injected speech ports."""

    def __init__(self, stt: SpeechToTextPort, tts: TextToSpeechPort) -> None:
        self.stt = stt
        self.tts = tts

    def intake(
        self,
        channel: Channel,
        payload: str,
        language: Language,
        audio: str | None = None,
    ) -> str:
        """Convert an inbound payload into text.

        For voice channels the audio (falling back to `payload`) is transcribed;
        all other channels return `payload` verbatim.
        """
        if channel is Channel.VOICE:
            return self.stt.transcribe(audio or payload, language)
        return payload

    def render(self, channel: Channel, message: str, language: Language) -> str:
        """Convert an outbound message for the target channel.

        For voice channels the message is synthesized to speech; all other
        channels return `message` verbatim.
        """
        if channel is Channel.VOICE:
            return self.tts.synthesize(message, language)
        return message
