"""Protocol and cancellation checks without GPU dependencies. python -m voice.check"""
import base64
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import threading
import unittest
import wave
import io
import importlib.util

from .server import chunks, make_server, normalize, validate, wav_bytes

class FakeEngine:
    device = 'test'
    def __init__(self): self.gate = threading.Lock()
    def generate(self, text, voice, speed):
        for segment in chunks(text):
            yield segment, b'\x01\x00' * 2400, False

class VoiceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FakeEngine()
        cls.server = make_server('127.0.0.1', 0, cls.engine)
        cls.port = cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
    def request(self, path, body=None, origin='null'):
        client = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        headers = {'Content-Type': 'application/json', 'Origin': origin}
        client.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        response = client.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        client.close()
        return result
    def test_normalization_preserves_numbers(self):
        self.assertEqual(normalize('**block-c**: 251.4 DD on 2026-06-04; 72°F. biofix'), 'Block C: 251.4 degree days on June 4, 2026; 72 degrees Fahrenheit. bio fix')
        self.assertEqual(list(chunks('At 251.4 degree days. Next sentence!')), ['At 251.4 degree days.', 'Next sentence!'])
        self.assertEqual(' '.join(chunks('word '*200)), ('word '*200).strip())
    def test_bad_requests(self):
        for body in ([], None, {}, {'input':'x','speed':True}, {'input':'x','speed':float('nan')}, {'input':'x','voice':[]}, {'input':'x'*2401}):
            with self.assertRaises(ValueError): validate(body)
        for body in ({'input':'x','speed':float('nan')}, [], {'input':'x','voice':'cloud'}):
            self.assertEqual(self.request('/stream', body)[0], 400)
    def test_stream(self):
        status, headers, data = self.request('/stream', {'input':'First. Second.'})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'null')
        frames = [json.loads(line) for line in data.splitlines()]
        self.assertEqual([f['type'] for f in frames], ['start','audio','audio','done'])
        self.assertEqual(len(base64.b64decode(frames[1]['pcm'])), 4800)
        self.assertEqual(frames[-1]['audio_seconds'], .2)
    def test_wav(self):
        status, _, data = self.request('/v1/audio/speech', {'input':'Hello.'})
        self.assertEqual(status, 200)
        with wave.open(io.BytesIO(data)) as f:
            self.assertEqual((f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getnframes()), (24000,1,2,2400))
    def test_busy_and_origin(self):
        self.engine.gate.acquire()
        try: self.assertEqual(self.request('/stream', {'input':'Hello'})[0], 429)
        finally: self.engine.gate.release()
        self.assertEqual(self.request('/stream', {'input':'Hello'}, 'https://untrusted.example')[0], 403)
        self.assertEqual(self.request('/health')[0], 200)
    @unittest.skipUnless(importlib.util.find_spec('soundfile'), 'codec checked in GPU image')
    def test_opus_roundtrip(self):
        import soundfile as sf
        status, _, data = self.request('/stream', {'input':'Hello.', 'response_format':'opus'})
        self.assertEqual(status, 200)
        frames = [json.loads(line) for line in data.splitlines()]
        frame = frames[1]
        self.assertEqual(frame['encoding'], 'opus')
        decoded, rate = sf.read(io.BytesIO(base64.b64decode(frame['audio'])))
        self.assertEqual(rate, 24000)
        self.assertEqual(len(decoded), 2400)
    def test_explicit_wav_format(self):
        self.assertEqual(self.request('/v1/audio/speech', {'input':'Hello.', 'response_format':'opus'})[0],400)
    def test_no_repo_file_exposure(self):
        for path in ('/../AGENTS.md', '/../../.env', '/voice/server.py'):
            self.assertEqual(self.request(path)[0], 404)
    def test_disconnect_releases_model(self):
        client = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        client.request('POST', '/stream', json.dumps({'input':'Hello. '*200}), {'Content-Type':'application/json'})
        client.getresponse().read(32)
        client.close()
        self.assertTrue(self.engine.gate.acquire(timeout=2))
        self.engine.gate.release()

if __name__ == '__main__': unittest.main()
