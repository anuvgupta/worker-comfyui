from .templates.stable_diffusion import build_workflow_loader

SD_CHECKPOINT_NAME = "juggernautXL_juggXILightningByRD.safetensors"
NEGATIVE_PROMPT = "text, watermark, blurry, low quality, bad quality"
SAMPLER_ALGORITHM = "dpmpp_sde"
SAMPLER_CFG = 1.5
SAMPLER_STEPS = 6
MAX_IMAGE_SIZE = 1024

load = build_workflow_loader(
    SD_CHECKPOINT_NAME,
    NEGATIVE_PROMPT,
    MAX_IMAGE_SIZE,
    SAMPLER_STEPS,
    SAMPLER_CFG,
    SAMPLER_ALGORITHM,
)
