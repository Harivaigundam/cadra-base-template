"""AI adapters — model routing and speech (simulated).

Implements the application's `ModelPort`, `SpeechToTextPort` and
`TextToSpeechPort` ports. No third-party dependencies; the language model and
speech services are simulated deterministically.

The `ModelRouter` encodes the platform decision that *highly confidential* data
must only be processed by self-hosted LLMs.
"""
from __future__ import annotations

from ..application.ports import ModelPort, SpeechToTextPort, TextToSpeechPort
from ..domain.model import DataClass, Language


class SelfHostedModel:
    """Language model adapter backed by a self-hosted deployment.

    Used for the most sensitive (highly confidential) data.
    """

    def generate(self, prompt: str, data_class: DataClass) -> str:
        """Return a deterministic simulated completion for `prompt`."""
        return f"[self-hosted:{data_class.value}] {prompt}"


class ApiModel:
    """Language model adapter backed by a third-party API deployment."""

    def generate(self, prompt: str, data_class: DataClass) -> str:
        """Return a deterministic simulated completion for `prompt`."""
        return f"[api:{data_class.value}] {prompt}"


class ModelRouter:
    """Routes generation to self-hosted or API models based on data class.

    Highly confidential data is kept on self-hosted models; everything else is
    allowed to use the API model.
    """

    def __init__(self, self_hosted: ModelPort, api: ModelPort) -> None:
        self.self_hosted = self_hosted
        self.api = api
        self.last_target = ""

    def generate(self, prompt: str, data_class: DataClass) -> str:
        """Route the request and record which target served it.

        Sets `self.last_target` to ``"self_hosted"`` or ``"api"`` so callers and
        tests can observe the routing decision.
        """
        if data_class is DataClass.HIGHLY_CONFIDENTIAL:
            self.last_target = "self_hosted"
            return self.self_hosted.generate(prompt, data_class)
        self.last_target = "api"
        return self.api.generate(prompt, data_class)


class KeywordSpeechToText:
    """Simulated speech-to-text adapter.

    There is no real audio pipeline in this template, so transcription simply
    echoes the provided audio transcript.
    """

    def transcribe(self, audio: str, language: Language) -> str:
        """Return the simulated transcript for `audio`."""
        return audio


class SimpleTextToSpeech:
    """Simulated text-to-speech adapter that marks the target language."""

    def synthesize(self, text: str, language: Language) -> str:
        """Return a simulated spoken rendering of `text`."""
        return f"[{language.value} TTS] {text}"
