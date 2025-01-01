import random

from . import calculate_dimensions

# Create loader for standard stable diffusion workflow
def build_workflow_loader(
    sd_checkpoint_name,
    negative_prompt,
    max_size,
    sampler_steps,
    sampler_cfg,
    sampler_algorithm="euler",
    sampler_scheduler="normal",
    sampler_denoise=1,
):

    # Loader for standard stable diffusion workflow
    def load(
        positive_prompt,
        aspect_ratio,
        job_id,
        filename_prefix
    ):

        filename_prefix = f"{filename_prefix}_{job_id}"

        random_seed = random.randint(10**14, 10**15 - 1)

        image_width, image_height = calculate_dimensions(max_size, aspect_ratio)

        workflow_data = {

            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                    "seed": random_seed,
                    "steps": sampler_steps,
                    "cfg": sampler_cfg,
                    "sampler_name": sampler_algorithm,
                    "scheduler": sampler_scheduler,
                    "denoise": sampler_denoise
                }
            },

            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": sd_checkpoint_name
                }
            },

            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": image_width,
                    "height": image_height,
                    "batch_size": 1
                }
            },

            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": positive_prompt
                }
            },

            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": negative_prompt
                }
            },

            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },

            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["8", 0],
                    "filename_prefix": filename_prefix
                }
            }

        }

        return workflow_data
    
    return load
