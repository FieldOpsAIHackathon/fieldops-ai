# FieldOps detector weights

`fieldops-yolo26s-v2.pt` — YOLO26s (NMS-free), 5 classes: `codling_moth`, `oriental_fruit_moth`,
`spotted_lanternfly`, `gnat`, `debris`. Only the first three are counted; gnats and debris are
detected so they are not mistaken for pests.

- **Trained** on 3,000 synthetic cards from `fieldops/synth_traps.py` (12 epochs, 960 px), then
  fine-tuned 4 epochs on those plus 2,000 phone-style versions (`make_dataset.py --phone 2000`).
- **Phone-style test** (200 photos, unseen seeds, `bash fieldops/yolo/run.sh phone-test`):
  count MAE codling 0.07, oriental fruit moth 0.04, lanternfly 0.00. v1 (no phone data) scored
  3.67 / 4.65 / 0.12 because scale and blur made it swap the two moth species.
- **Known gap**: all training data is synthetic. Real trap photos are the next fine-tune.
- sha256 `af43eaed1d6c6e5859124294c07522d69f35e82ab94aec210c4d3ab15bee6123`
