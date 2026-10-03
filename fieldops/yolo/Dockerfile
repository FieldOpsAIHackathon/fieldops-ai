FROM nvcr.io/nvidia/vllm@sha256:9204569b17ee4c0eff75194b8e6e458479c8aee18953b5ab9cf359fcdac659e2
# NVIDIA's GB10 torch/torchvision come from this image; add ultralytics and a headless OpenCV.
RUN pip install --no-cache-dir ultralytics \
 && pip uninstall -y opencv-python \
 && pip install --no-cache-dir --force-reinstall --no-deps opencv-python-headless
# The image's cuDNN 9.22 lacks libcudnn_engines_precompiled, so many conv kernels fail.
# Restore it from NVIDIA's matching cuDNN wheel (609 MB download, one library kept).
RUN pip download --no-deps --no-cache-dir -d /tmp/cudnn nvidia-cudnn-cu13==9.22.0.52 \
 && python3 -c "import zipfile,glob; zipfile.ZipFile(glob.glob('/tmp/cudnn/*.whl')[0]).extract('nvidia/cudnn/lib/libcudnn_engines_precompiled.so.9', '/tmp/cudnn')" \
 && mv /tmp/cudnn/nvidia/cudnn/lib/libcudnn_engines_precompiled.so.9 /usr/lib/aarch64-linux-gnu/libcudnn_engines_precompiled.so.9.22.0 \
 && cd /usr/lib/aarch64-linux-gnu \
 && ln -sf libcudnn_engines_precompiled.so.9.22.0 libcudnn_engines_precompiled.so.9 \
 && ln -sf libcudnn_engines_precompiled.so.9 libcudnn_engines_precompiled.so \
 && ldconfig && rm -rf /tmp/cudnn
ENTRYPOINT []
