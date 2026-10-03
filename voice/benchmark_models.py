"""Run inside the GPU image; writes real audio and timings, never estimated scores."""
import argparse
import json
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--engine', choices=['kokoro', 'qwen'], default='kokoro')
p.add_argument('--models', default='/models')
p.add_argument('--out', default='/samples')
a = p.parse_args()
import numpy as np
import soundfile as sf
import torch

torch.set_num_threads(4)
root = Path(a.models)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
start = time.perf_counter()
if a.engine == 'kokoro':
    from kokoro import KModel, KPipeline
    model = KModel(config=str(root/'kokoro/config.json'), model=str(root/'kokoro/kokoro-v1_0.pth')).to('cuda').eval()
    pipe = KPipeline(lang_code='a', model=model)
    voice = torch.load(root/'kokoro/voices/af_heart.pt', weights_only=True)
    def generate(text):
        return np.concatenate([x.audio.cpu().numpy() for x in pipe(text, voice=voice, speed=1.0)]), 24000
else:
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(str(root/'qwen'), device_map='cuda:0', dtype=torch.bfloat16, attn_implementation='sdpa')
    def generate(text):
        wavs, sr = model.generate_custom_voice(text=text, language='English', speaker='Aiden', instruct='Speak warmly and naturally, like a knowledgeable colleague giving a concise orchard update. Calm, conversational, clear. No announcer voice.', max_new_tokens=600, do_sample=False)
        return wavs[0], sr
print(json.dumps({'engine':a.engine, 'load_seconds':round(time.perf_counter()-start,3)}), flush=True)
texts = ['Your orchard update is ready.', 'Block C has reached the spray window. The degree-day clock is now at two hundred and fifty.', 'Good morning. Codling moth activity is rising in Block C. Biofix is confirmed, and the degree-day clock is running. I will let you know when the treatment window opens.']
for i, text in enumerate(texts):
    start = time.perf_counter()
    with torch.inference_mode():
        wav, sr = generate(text)
    elapsed=time.perf_counter()-start
    sf.write(out/f'{a.engine}-{i}.wav', wav, sr)
    print(json.dumps({'engine':a.engine, 'text':text, 'seconds':round(elapsed,3), 'audio_seconds':round(len(wav)/sr,3), 'rtf':round(elapsed/(len(wav)/sr),3), 'sample_rate':sr, 'peak':float(np.max(np.abs(wav))), 'gpu_allocated_gb':round(torch.cuda.memory_allocated()/1e9,3)}), flush=True)
