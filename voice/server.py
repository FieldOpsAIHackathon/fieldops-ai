"""Warm, local Kokoro speech service. Run with python -m voice.server.

No cloud fallback. The decision engine never imports this module. Models and
voices must already be on disk; inference starts with Hugging Face offline.
"""
import argparse
import base64
from collections import OrderedDict
from datetime import date
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
    os.environ[name] = '1'

RATE = 24000
MAX_TEXT = 2400
MAX_BODY = 16384
ROOT = Path(__file__).resolve().parents[1]
VOICES = {
    'orchard': {'name': 'Orchard', 'description': 'Warm, clear and conversational', 'mix': [('af_heart', .7), ('af_bella', .3)]},
    'heart': {'name': 'Heart', 'description': 'The familiar Coach voice', 'mix': [('af_heart', 1.)]},
    'bella': {'name': 'Bella', 'description': 'Soft and relaxed', 'mix': [('af_bella', 1.)]},
    'fenrir': {'name': 'Fenrir', 'description': 'Measured and grounded', 'mix': [('am_fenrir', 1.)]},
}


def normalize(text):
    """Speak display text clearly without changing its underlying facts."""
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?m)^\s*[-*#>]+\s*', '', text)
    text = re.sub(r'[*`]', '', text)
    def spoken_date(match):
        try:
            d = date.fromisoformat(match[0])
            return f'{d.strftime("%B")} {d.day}, {d.year}'
        except ValueError:
            return match[0]
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', spoken_date, text)
    text = re.sub(r'\bblock[-_]([a-z])\b', lambda m: f'Block {m[1].upper()}', text, flags=re.I)
    text = re.sub(r'\bDD\b', 'degree days', text)
    text = text.replace('°F', ' degrees Fahrenheit').replace('°C', ' degrees Celsius')
    text = re.sub(r'\bbiofix\b', 'bio fix', text, flags=re.I)
    text = text.replace('_', ' ').replace('—', ', ').replace('–', ' to ')
    return re.sub(r'\s+', ' ', text).strip()


def chunks(text):
    # Preserve full sentences whenever possible, and never split decimal numbers.
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        while len(sentence) > 220:
            cut = max(sentence.rfind(', ', 70, 200), sentence.rfind('; ', 70, 200))
            if cut < 0:
                cut = sentence.rfind(' ', 70, 200)
            if cut < 0:
                cut = 200
            else:
                cut += 1
            yield sentence[:cut].strip()
            sentence = sentence[cut:].strip()
        if sentence:
            yield sentence


def validate(body):
    if not isinstance(body, dict):
        raise ValueError('Send a JSON object.')
    text = body.get('input', body.get('text', ''))
    voice = body.get('voice', 'orchard')
    speed = body.get('speed', 1.0)
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_TEXT:
        raise ValueError(f'Text must contain 1–{MAX_TEXT} characters.')
    if not isinstance(voice, str) or voice not in VOICES:
        raise ValueError('Choose a listed voice.')
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or not .85 <= speed <= 1.15:
        raise ValueError('Speed must be between 0.85 and 1.15.')
    text = normalize(text)
    if not text:
        raise ValueError('There is no speakable text.')
    return text, voice, round(float(speed), 2)


class Engine:
    def __init__(self, model_dir, device='cuda'):
        import torch
        from kokoro import KModel, KPipeline
        torch.set_num_threads(4)
        self.torch = torch
        self.device = device
        self.gate = threading.Lock()
        self.cache = OrderedDict()
        self.cache_bytes = 0
        root = Path(model_dir) / 'kokoro'
        model = KModel(config=str(root/'config.json'), model=str(root/'kokoro-v1_0.pth')).to(device).eval()
        self.pipe = KPipeline(lang_code='a', model=model, repo_id='hexgrad/Kokoro-82M')
        self.voices = {}
        for name, spec in VOICES.items():
            self.voices[name] = sum(torch.load(root/'voices'/f'{v}.pt', weights_only=True) * weight for v, weight in spec['mix'])
        # Pay model/CUDA first-use costs before advertising readiness.
        for _ in self.generate('Your orchard update is ready.', 'orchard', 1.0):
            pass

    def generate(self, text, voice, speed):
        import numpy as np
        for segment in chunks(text):
            key = (segment, voice, speed)
            cached = self.cache.get(key)
            if cached is not None:
                self.cache.move_to_end(key)
                yield segment, cached, True
                continue
            parts = []
            with self.torch.inference_mode():
                for result in self.pipe(segment, voice=self.voices[voice], speed=speed):
                    samples = result.audio.cpu().numpy()
                    if not np.isfinite(samples).all():
                        raise RuntimeError('Model produced invalid samples.')
                    parts.append((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
            pcm = b''.join(parts)
            if not pcm:
                raise RuntimeError('Model produced no audio.')
            self.cache[key] = pcm
            self.cache_bytes += len(pcm)
            while self.cache_bytes > 32 * 1024 * 1024 or len(self.cache) > 128:
                _, old = self.cache.popitem(last=False)
                self.cache_bytes -= len(old)
            yield segment, pcm, False


def wav_bytes(pcm):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 closes at EOF; flushed NDJSON lines are delivered progressively.
    server_version = 'FieldOpsVoice/1.0'

    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def log_message(self, fmt, *args):
        # Request paths/status only: never log the text or audio.
        super().log_message(fmt, *args)

    def allowed(self):
        origin = self.headers.get('Origin')
        return origin is None or origin in self.server.origins

    def send_headers(self, code, content_type, length=None):
        self.send_response(code)
        origin = self.headers.get('Origin')
        if origin in self.server.origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if length is not None:
            self.send_header('Content-Length', str(length))
        self.end_headers()

    def json(self, code, value):
        data = json.dumps(value).encode()
        self.send_headers(code, 'application/json', len(data))
        self.wfile.write(data)

    def do_OPTIONS(self):
        if not self.allowed():
            return self.json(403, {'error': 'Origin not allowed.'})
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', 'null'))
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '600')
        self.end_headers()

    def do_GET(self):
        if not self.allowed():
            return self.json(403, {'error': 'Origin not allowed.'})
        path = urlsplit(self.path).path
        if path == '/health':
            return self.json(200, {'ready': True, 'engine': 'Kokoro-82M', 'device': self.server.engine.device, 'sample_rate': RATE, 'offline': True, 'voices': [{'id': k, 'name': v['name'], 'description': v['description']} for k, v in VOICES.items()]})
        if path == '/':
            path = '/voice.html'
        # Serve only dashboard files, never repository secrets/model weights.
        public_root = ROOT/'dashboard'
        relative = path.lstrip('/')
        if path.startswith('/data/traps/'):
            public_root = ROOT/'data/traps'
            relative = path[len('/data/traps/'):]
        candidate = (public_root/relative).resolve()
        if not candidate.is_relative_to(public_root.resolve()) or not candidate.is_file():
            return self.json(404, {'error': 'Not found.'})
        import mimetypes
        body = candidate.read_bytes()
        self.send_headers(200, mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream', len(body))
        self.wfile.write(body)

    def do_POST(self):
        if not self.allowed():
            return self.json(403, {'error': 'Origin not allowed.'})
        path = urlsplit(self.path).path
        if path not in ('/stream', '/v1/audio/speech'):
            return self.json(404, {'error': 'Not found.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise ValueError('Request body is too large or empty.')
            self.connection.settimeout(15)
            request = json.loads(self.rfile.read(length))
            text, voice, speed = validate(request)
            encoding = request.get('response_format', 'wav' if path == '/v1/audio/speech' else 'pcm')
            if encoding not in (('wav',) if path == '/v1/audio/speech' else ('pcm', 'opus')):
                raise ValueError('Unknown audio format.')
        except (ValueError, TypeError, TimeoutError):
            return self.json(400, {'error': 'Use input (1–2400 characters), a listed voice, and speed 0.85–1.15.'})
        engine = self.server.engine
        if not engine.gate.acquire(blocking=False):
            return self.json(429, {'error': 'Voice is finishing another request. Try again shortly.'})
        started = time.perf_counter()
        streaming = False
        try:
            generator = engine.generate(text, voice, speed)
            if path == '/v1/audio/speech':
                body = wav_bytes(b''.join(pcm for _, pcm, _ in generator))
                self.send_headers(200, 'audio/wav', len(body))
                self.wfile.write(body)
                return
            first = next(generator)
            first_ms = round((time.perf_counter()-started)*1000)
            self.send_headers(200, 'application/x-ndjson')
            streaming = True
            def emit(value):
                self.wfile.write(json.dumps(value).encode()+b'\n')
                self.wfile.flush()
            emit({'type': 'start', 'sample_rate': RATE, 'voice': voice, 'first_audio_ms': first_ms})
            import itertools
            duration = 0
            for segment, pcm, cached in itertools.chain([first], generator):
                duration += len(pcm) / (2 * RATE)
                if encoding == 'opus':
                    import numpy as np
                    import soundfile as sf
                    encoded = io.BytesIO()
                    sf.write(encoded, np.frombuffer(pcm, dtype='<i2'), RATE, format='OGG', subtype='OPUS')
                    emit({'type': 'audio', 'text': segment, 'audio': base64.b64encode(encoded.getvalue()).decode(), 'encoding': 'opus', 'cached': cached})
                else:
                    emit({'type': 'audio', 'text': segment, 'pcm': base64.b64encode(pcm).decode(), 'encoding': 'pcm', 'cached': cached})
            emit({'type': 'done', 'synthesis_ms': round((time.perf_counter()-started)*1000), 'audio_seconds': round(duration, 3)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass  # A stopped browser request releases the model at the next chunk.
        except Exception as exc:
            print(f'Speech failed: {type(exc).__name__}: {exc}', flush=True)
            if not streaming:
                self.json(503, {'error': 'Local voice could not generate audio.'})
            else:
                try:
                    emit({'type': 'error', 'error': 'Local voice could not finish the audio.'})
                except OSError:
                    pass
        finally:
            engine.gate.release()


def make_server(host, port, engine, origins=()):
    server = ThreadingHTTPServer((host, port), Handler)
    server.engine = engine
    server.origins = {'null', 'file://', f'http://127.0.0.1:{port}', f'http://localhost:{port}', *origins}
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8790)
    parser.add_argument('--models', default=os.environ.get('FIELDOPS_VOICE_MODELS', '/models'))
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--origin', action='append', default=[])
    args = parser.parse_args()
    engine = Engine(args.models, args.device)
    server = make_server(args.host, args.port, engine, args.origin)
    print(f'FieldOps voice ready: http://{args.host}:{args.port}, device={args.device}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
