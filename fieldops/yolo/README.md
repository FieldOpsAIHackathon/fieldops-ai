# Vision lane: counting pests with YOLO26

A trap photo goes in and per-species counts come out, in the
[AGENTS.md](../../AGENTS.md) contract shape. It is deterministic (fixed weights, fixed confidence
threshold, no test-time augmentation) and runs on the GB10 GPU. A Telegram photo comes back in a few
seconds, most of it the agent's turn.

```
 Telegram photo ──▶ OpenClaw agent ──▶ POST /count (fieldops.api :8765) ──▶ fieldops.vision (:8767, GPU)
                     (fieldops-tools skill)                                     │ YOLO26s
                                                                                ▼
                       reply: "50 codling moth, 12 oriental fruit moth"  ◀── counts + boxed image
```

## The model

- **YOLO26s** (Ultralytics 8.4), 10 M parameters, 960 px input. YOLO26 is NMS-free: it outputs
  final boxes directly, so there is no overlap threshold that could merge two touching moths.
- **5 classes**: `codling_moth`, `oriental_fruit_moth`, `spotted_lanternfly`, `gnat`, `debris`.
  Only the first three are counted. Gnats and debris are trained as classes so the model learns
  what they are, instead of counting them as pests.
- **Weights**: [`models/fieldops-yolo26s-v2.pt`](../../models/), with a model card in
  [`models/README.md`](../../models/README.md).
- **Why YOLO rather than the VLM** (Qwen3.6 on vLLM can see images): a detector gives the same
  count every time, gives boxes you can show on screen, and can be scored against ground truth. A
  VLM describing a photo cannot be trusted to count 50 moths exactly.

## Training data: all synthetic, with exact labels

`fieldops/synth_traps.py` already drew cards with known insects. `render()` returns a pixel box
for every insect, gnat and piece of debris, so labels are exact and free.

| Split | Images | What |
|---|---|---|
| `train` / `val` | 3,000 / 400 | Clean rendered cards, 0 to 60 codling moths, 0 to 30 oriental fruit moths, 0 to 5 lanternflies, plus gnats and debris |
| `train_phone` / `val_phone` | 2,000 / 300 | The same kind of card made to look like a phone photo, with every box moved through the same warp |
| phone test | 200 | Phone-style, **seeds no training split uses** (3M+, versus 1M, 2M, 4M and 5M) |

"Phone-style" means a desk background, perspective tilt, rotation, focus or motion blur, uneven
light and glare, colour cast, sensor noise, JPEG at quality 55 to 85, and phone resolutions (see
`phone_photo()` in `phone_test.py`). Everything is seeded, so re-running reproduces the dataset
exactly.

## Results, and the overfitting we found

| | v1 (clean cards only) | **v2 (+ phone-style fine-tune)** |
|---|---|---|
| 6 reference cards in `data/traps/` | 17/18 counts exact | 13/18 exact (misses a few oriental fruit moths) |
| 200 phone-style photos: codling moth MAE | 3.67 (95/200 exact) | **0.07 (189/200)** |
| oriental fruit moth MAE | 4.65 (87/200) | **0.04 (192/200)** |
| spotted lanternfly MAE | 0.12 | **0.00** |

v1 scored mAP50 0.995 on its validation set and still failed on phone-style photos. It had learned
our renderer: codling moths and oriental fruit moths differ mostly in size, and once a photo changed
the scale or blurred the orange wing tip, v1 called codling moths oriental fruit moths. A
validation set drawn by the same generator could not catch that; the phone test did.

**Be honest about what this proves.** The phone test uses the same kinds of effects v2 trained on
(different seeds), so 0.07 is a best case. Real photos of real traps are the true test and the next
fine-tune. No public dataset has boxed codling moths. Public sticky-trap sets cover other pests,
such as greenhouse whiteflies (4TU) and grapevine leafhoppers (Zenodo).

## Running it

Everything runs in the `local/fieldops-yolo` container, which has NVIDIA's GB10 PyTorch build plus
ultralytics. `run.sh` mounts the repo at `/work`, the dataset at `/data` and runs at `/runs`.

```bash
docker build -t local/fieldops-yolo fieldops/yolo/            # once (pulls a 609 MB cuDNN wheel)

bash fieldops/yolo/run.sh serve                                # counting service on 127.0.0.1:8767
curl --data-binary @card.jpg "localhost:8765/count?trap_id=block-c-04"   # via the tools API
bash fieldops/yolo/run.sh vision data/traps/*.jpg              # one-off: contract records per image
bash fieldops/yolo/run.sh eval                                 # score the 6 reference cards
bash fieldops/yolo/run.sh phone-test --n 200                   # the overfitting check
```

`fieldops.vision` saves every photo and a pest-only boxed copy under `data/vision/`, and appends its
records to `data/vision/counts.jsonl`. It writes to the SQLite store only with `--to-store`, so a
stray demo photo cannot move `decide`'s spray dates.

## Retraining

```bash
python -m fieldops.yolo.make_dataset --train 3000 --val 400 --phone 2000   # ~2 min, 20 cores
bash fieldops/yolo/run.sh train                                    # from scratch: 30 min budget
bash fieldops/yolo/run.sh train --model /work/models/fieldops-yolo26s-v2.pt \
     --name traps_v3 --hours 0.3 --lr0 0.002                       # fine-tune
bash fieldops/yolo/run.sh phone-test --weights /runs/traps_v3/weights/best.pt
```

To add real photos, put YOLO-format labels under `~/hackathon-stack/yolo-data/{images,labels}/train_real`
and add `images/train_real` to `train:` in `data.yaml`.

## Gotchas we hit on the GB10

- **The vLLM image's cuDNN is incomplete.** It lacks `libcudnn_engines_precompiled.so`, so FP16
  and backward convolutions fail with "unable to find an engine" or `SUBLIBRARY_UNAVAILABLE`. The
  Dockerfile restores that one library from NVIDIA's matching `nvidia-cudnn-cu13==9.22.0.52` wheel.
  `train.py` and `count.py` turn cuDNN off if the library is missing, which works but is about 30%
  slower.
- **Ultralytics' default settings folder is root-owned in the image**, so `run.sh` points
  `YOLO_CONFIG_DIR` and `HOME` at the runs folder.
- **Closing a terminal does not stop a `docker run`.** The vision container is named
  `fieldops-vision` and replaced on every start, so a leftover can never hold port 8767.
- **OpenClaw freezes a session's skills at session start.** After changing `openclaw/fieldops-tools`,
  reset the shared DM session once: `nemoclaw fieldops agent --agent main -m "/new"`.
