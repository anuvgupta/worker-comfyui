from .templates.stable_diffusion import build_workflow_loader

SD_CHECKPOINT_NAME = "v1-5-pruned-emaonly.safetensors"
NEGATIVE_PROMPT = "text, watermark, blurry, low quality, bad quality"
SAMPLER_CFG = 9
SAMPLER_STEPS = 40
MAX_IMAGE_SIZE = 768

# Create 
load = build_workflow_loader(
    SD_CHECKPOINT_NAME,
    NEGATIVE_PROMPT,
    MAX_IMAGE_SIZE,
    SAMPLER_STEPS,
    SAMPLER_CFG,
)
