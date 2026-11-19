from pathlib import Path

from cutlab import config
from cutlab.engines import tts


def test_fish_free_model_payload_and_output(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TTS_ENGINE", "fish")
    monkeypatch.setattr(config, "FISH_API_KEY", "test-key")
    monkeypatch.setattr(config, "FISH_MODEL", "s2.1-pro-free")
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return b"RIFF-fish-audio"

    def urlopen(request, timeout):
        captured["body"] = request.data.decode()
        captured["model"] = request.headers["Model"]
        return Response()

    monkeypatch.setattr(tts.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(tts, "run_ffmpeg", lambda args: Path(args[-1]).write_bytes(Path(args[1]).read_bytes()))
    output = tmp_path / "voice.wav"
    assert tts.synthesize("Hello", output) == "fish"
    assert output.exists() and captured["model"] == "s2.1-pro-free"
    assert "reference_id" not in captured["body"]


def test_fish_failure_falls_back_to_piper(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TTS_ENGINE", "fish")
    monkeypatch.setattr(config, "FISH_API_KEY", "test-key")
    monkeypatch.setattr(tts, "_run_fish", lambda *_: (_ for _ in ()).throw(RuntimeError("quota")))
    monkeypatch.setattr(tts, "synth_piper", lambda text, path: path.write_bytes(b"piper"))
    output = tmp_path / "voice.wav"
    assert tts.synthesize("Fallback", output) == "piper"
    assert output.read_bytes() == b"piper"
