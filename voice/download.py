"""One-time connected setup. Inference uses these local files with HF offline."""
import argparse
import hashlib
import json
from pathlib import Path

KOKORO_FILES = ['config.json', 'kokoro-v1_0.pth', 'voices/af_heart.pt', 'voices/af_bella.pt', 'voices/am_fenrir.pt', 'LICENSE', 'README.md', 'VOICES.md']

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--models', default='/models')
    p.add_argument('--qwen', action='store_true', help='Also download the optional benchmark model')
    args = p.parse_args()
    from huggingface_hub import HfApi, snapshot_download
    root = Path(args.models)
    specs = [('hexgrad/Kokoro-82M', 'kokoro', KOKORO_FILES)]
    if args.qwen:
        specs.append(('Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', 'qwen', None))
    for repo, directory, patterns in specs:
        revision = HfApi().model_info(repo).sha
        snapshot_download(repo, revision=revision, local_dir=root/directory, allow_patterns=patterns)
        manifest = {'repository':repo, 'revision':revision, 'files':{}}
        for file in sorted((root/directory).rglob('*')):
            if not file.is_file() or '.cache' in file.parts or file.name=='manifest.json':
                continue
            with file.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            manifest['files'][str(file.relative_to(root/directory))] = digest
        (root/directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        print(f'{repo}@{revision}: recorded hashes for {len(manifest["files"])} local files')

if __name__ == '__main__': main()
