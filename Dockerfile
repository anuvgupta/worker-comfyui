# dockerfile

FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

WORKDIR /

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PATH=/usr/local/cuda/bin:/opt/venv/bin:$PATH \
    ENVIRONMENT=PRODUCTION \
    COMFYUI_ROOT=/comfyui

# Install Python, system dependencies, and CUDA
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    git \
    python3.10 \
    python3.10-venv \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    wget && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment for Python and install requirements
RUN python3.10 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip

# Copy the Python dependencies (requirements.txt) and install
RUN /opt/venv/bin/pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Clone ComfyUI and install its dependencies
RUN git clone https://github.com/comfyanonymous/ComfyUI.git ${COMFYUI_ROOT} && \
    cd ${COMFYUI_ROOT} && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# download models
# SD Classic 1.5
# RUN wget --show-progress --progress=dot:giga -O /comfyui/models/checkpoints/v1-5-pruned-emaonly.safetensors https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
# SDXL Lightning 4-step
# RUN wget --show-progress --progress=dot:giga -O /comfyui/models/checkpoints/sdxl_lightning_4step.safetensors https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step.safetensors
# SDXL Lightning 8-step
# RUN wget --show-progress --progress=dot:giga -O /comfyui/models/checkpoints/sdxl_lightning_8step.safetensors https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_8step.safetensors
# Juggernaut XL Lightning, Version XI
# RUN wget --show-progress --progress=dot:giga -O /comfyui/models/checkpoints/juggernautXL_juggXILightningByRD.safetensors https://civitai.com/api/download/models/920957?type=Model&format=SafeTensor&size=full&fp=fp16
# TODO: Add your models here if not using network volume


# Copy the Python dependencies (requirements.txt) and install
COPY requirements.txt /requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /requirements.txt

# Copy application code
RUN mkdir -p /app
COPY src/ /app/
RUN chmod +x /app/main.sh

# Set the final command
CMD ["/app/main.sh"]
