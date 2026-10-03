FROM nvcr.io/nvidia/vllm@sha256:9204569b17ee4c0eff75194b8e6e458479c8aee18953b5ab9cf359fcdac659e2
# Keep NVIDIA's GB10 torch/torchvision; add ultralytics and a headless OpenCV.
RUN pip install --no-cache-dir ultralytics \
 && pip uninstall -y opencv-python \
 && pip install --no-cache-dir --force-reinstall --no-deps opencv-python-headless \
 && python3 -c "import torch, ultralytics, cv2; print('ok', torch.__version__, ultralytics.__version__, cv2.__version__)"
ENTRYPOINT []
