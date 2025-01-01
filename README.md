<div align="center">

<h1>ComfyUI | Worker</h1>

This worker is a RunPod worker that uses the Stable Diffusion model for AI tasks. The worker is built upon the Stable Diffusion ComfyUI by comfyanonymous, which is a user interface for Stable Diffusion AI models and an alternative to the Stable Diffusion Web UI by automatic111.

This worker package is based on https://github.com/runpod-workers/worker-a1111

</div>

## Model

Models are auto downloaded in the Dockerfile. To add more models, add a similar line in the Dockerfile, in the "download models" section, and make sure to also download to your local ComfyUI folder if testing locally.

```
RUN wget --show-progress --progress=dot:giga -O /comfyui/models/checkpoints/<model_file_name> https://huggingface.co/<username>/<model_name>/resolve/main/<model_file_name>
```

Alternatively you can follow the [steps below](network-volume) to download files to a network volume instead, which will help reduce your container size and your container deployment times to the minimum.

## Serverless Handler

The serverless handler (`handler.py`) is a Python script that handles inference requests. It defines a function handler(event) that takes an inference request, runs the inference using a Stable Diffusion model via a workflow within ComfyUI, and returns the output.

## Building the Worker

The worker is built using a Dockerfile. The Dockerfile specifies the base image, environment variables, system package dependencies, Python dependencies, model downloads, and the steps to install and setup the ComfyUI Stable Diffusion Web UI. It also downloads models and sets up the API server.

The Python dependencies are specified in requirements.txt. The primary dependency is `runpod`.

## Build and run in production

To build for production, we can use the Dockerfile. There are two options for this:

1. Build the Docker container locally & push to DockerHub using Docker CLI or Docker UI
2. OR Run a GitHub action to use Docker BuilderX to efficiently automate this. Please see setup steps below for how to set up the GitHub actions for this.

Then, you can:

-   Deploying a new image

    -   Go to RunPod website
    -   Create a new serverless endpoint
    -   Set your options for scaling & cold starts
        -   To reduce cold starts from ComfyUI startup & loading models into memory, increase the idle timeout to a couple minutes or increase # active workers. This is not free but its a minor tradeoff for low latency, if you are testing often or if you have sporadic traffic patterns.
    -   Then set the container image source to `<your_dockerhub_username>/<your_dockerhub_reponame>:latest`
    -   (Optional) Set up optional environment variables on the same page (or you can add them later).

        ```
        APP_NAME="<your_comfyui_app_name>"                       # Defaults to "APP"
        COMFYUI_JOB_TIMEOUT_SEC="<your_desired_job_timeout>"     # Defaults to 180 sec (3 min)
        ```

    -   (Optional) Enable health check, S3 upload, network volumes, etc. if desired, by setting required environment variables on the same page (or you can add them later). See below sections for details.
    -   Click "Create Endpoint"

-   Deployment verification

    -   Monitor the logs for your idle workers to ensure no errors in container setup
    -   Send a test request with an example prompt & monitor logs
    -   If the function returns successfully, then check if the resulting base64 or S3 link is valid & displays a non-empty image
    -   You are all set! Take the `api.runpod.ai` URL including your endpoint ID, and use it freely in your frontends or backends. You will need to set up an API key for your app to access RunPod, see RunPod docs [here](https://docs.runpod.io/get-started/api-keys)

-   Deploying an update

    -   This is for new workflows/models, or any code updates

    -   Rebuild & push the container (or just trigger the GitHub action via commit or via GitHub website, if you have GitHub actions set up)
    -   Then go to RunPod Serverless page, go to your serverless endpoint, click "New Release" from the 3-dot menu on top right
    -   Then instead of entering `<your_dockerhub_username>/<your_dockerhub_reponame>:latest`, you should enter `<your_dockerhub_username>/<your_dockerhub_reponame>:<your_dockerhub_version_tag>` where the version tag is unique to that build (the `latest` tag always refers to the latest build but RunPod requires the version tag to change, in order to deploy a new image).
        -   Go to this page to get the tag: `https://hub.docker.com/r/<your_dockerhub_username>/<your_dockerhub_reponame>/tags`
        -   If you have GitHub actions set up, the GitHub action will add a new version tag for each pushed container in the format of `v1.0.xx` where `xx` is the GitHub actions run number, so you can use that.
        -   If not using GitHub actions, please add a new tag on your `latest` image from Docker CLI or UI, so it can be deployed via RunPod.

### Build and run locally

To build locally, you need to manually install Python, ComfyUI, dependency packages, and any model files.

-   Install latest ComfyUI and Python (at least 3.10) locally
-   Activate python env for ComfyUI via conda or venv
-   Install reqs for ComfyUI by running `pip install requirements.txt` from your local ComfyUI folder
-   Install reqs for this worker with `pip install requirements.txt` from this folder
-   (Optional) Set up optional environment variables in your local shell.

    ```
    APP_NAME="<your_comfyui_app_name>"                          # Defaults to "APP"
    COMFYUI_JOB_TIMEOUT_SEC="<your_desired_job_timeout>"        # Defaults to 180 sec (3 min)
    PYTHON_PATH_DEV="<path_to_local_python_venv_exe>"           # Defaults to "/usr/bin/python3"
    COMFYUI_PATH_DEV="<path_to_local_comfyui_installation>"     # Defaults to "~/comfyui"
    ```

-   (Optional) Enable health check, S3 upload, network volumes etc. if desired, by setting required environment variables in local shell. See below sections for details.
-   The worker can be run using the main.sh script. This script starts the system and runs the serverless handler script. In local testing, this starts a local development server you can access at localhost:8000 to test the `/run` and `/status` APIs.
    -   Start the development server by running `ENV=DEVELOPMENT src/main.sh` in your shell

### Health check

If you want to test your Runpod serverless environment without launching ComfyUI, ie. just to test the networking setup, connectivity, permissions, etc. then you can enable health check mode which will run the worker without ComfyUI, and will return `OK` from the `/run` endpoint.

N.B: The models will still be downloaded, you can comment that out of the Dockerfile as well to save time in testing with health check.

To enable health check mode, set this environment variable in Runpod settings & in your local shell:

```
HEALTH_CHECK_MODE="TRUE"
```

After setting this up, deploy/redeploy your serverless function to see if it works.

### S3 upload

Output images by default are returned in base64 format form the serverless API. To instead upload them to an S3 bucket and return a link from the serverless API, please set the following environment variables in Runpod settings & in your local shell:

```
ENABLE_S3_UPLOAD="TRUE"
AWS_ACCESS_KEY="<aws-access-key-contents>"
AWS_SECRET_KEY="<aws-secret-key-contents>"
AWS_BUCKET_NAME="<aws-bucket-name>"
AWS_REGION="<aws-bucket-upload-region>"
```

-   To get the bucket name, create a bucket in AWS console's S3 page, and allow public read permissions (list, get) to all objects of the bucket.
-   To get the access key and secret key, create an IAM user with read & write permissions (list, get, put) on all objects of the bucket, and then create an access key for that IAM user. Save the resulting access key & secret key to a file outside of this repository.
-   To get the AWS region, actually AWS region is not needed, it iwll default to `us-east-1`. If you want to use a different region for the S3 upload, you can change it.

After setting this up, deploy/redeploy your serverless function to see if it works.

### GitHub actions

Please add these secret vars in your Github account's settings to enable the DockerHub build & push action on commit & pull request:

```
DOCKERHUB_USERNAME="your_dockerhub_username"
DOCKERHUB_REPO_NAME="your_dockerhub_repo_name
DOCKERHUB_TOKEN="your_dockerhub_personal_access_token"
```

Then push a commit to test if it works.

### Network volume

To reduce build times further, you can enable a network volume on your serverless instance and download the models there. To do that, you will need to:

1. Temporarily create a runpods pod endpoint (non-serverless) using your container image.
2. Then SSH to the endpoint using a public key or RunPod web SSH.
3. Go to the network volume by running `cd /workspace`
4. Create a folder for your models, ie. `mkdir models`
5. Create subfolders for model types, ie `mkdir models/checkpoints`
    - Please note, you need to stay consistent with the names for ComfyUI model type folders, or else your models will not be found. The naming is inconsistent, sometimes plural sometimes singular. Use these names: `checkpoints, controlnet, loras, vae` and for the full list see the folder names in the official repository: https://github.com/comfyanonymous/ComfyUI/tree/master/models
6. Download your models into the appropriate folders with `wget` or anything else
    - If you have your models in a separate folder/drive on your local computer, you can organize it as mentioned in previous steps & link it to ComfyUI with `MODEL_CACHE_PATH_DEV`
7. Exit the SSH session
8. Terminate the instance - IMPORTANT - do this immediately or else you will lose money, these instances are expensive
9. Enable this flag in environment variables:

    ```
    ENABLE_NETWORK_VOLUME="TRUE"
    ```

10. (Optional) Add this flag to environment variables:

    ```
    MODEL_CACHE_PATH_DEV="<path_to_local_model_cache>"
    ```

11. Remove or comment out the model downloads from the Dockerfile
12. Deploy/redeploy your serverless function to see if this works

## API

The API follows standard Runpod format.

### `/run` endpoint

You can generate images by querying the `/run` endpoint with a POST request with this JSON data:

```
{
    "input": {
        "prompt": "girl sitting on grassy hill on a sunny day, with massive clouds in a big blue sky in the background, dreamy anime art style"
    }
}
```

To specify a workflow, you can call out the name. By default the worker will use `sd_1_5` which is the standard workflow using Stable Diffusion 1.5, 768x768 image, Euler algorithm with Normal scheduler.

```
{
    "input": {
        "prompt": "girl sitting on grassy hill on a sunny day, with massive clouds in a big blue sky in the background, dreamy anime art style",
        "workflow": "sdxl_lightning_4step"
    }
}
```

The output will include the starting state and the job ID which can be used to retrieve status updates & the final result:

```
{
  "id": "39d52364-09b0-466c-b6e8-3015ac9f671c-u1",
  "status": "IN_QUEUE"
}
```

### `/status` endpoint

The output should be retrieved from the `/status/:job_id` endpoint with a GET request with the job ID in the URL.

It will look different based on what stage the job is at, so it should be polled.

When polling, right after the job is created, the output will at first look like this:

```
{
    "id": "002edd2a-15f2-4f9d-917b-3f79961d1ad7-u1",
    "status": "IN_QUEUE"
}
```

After the job is picked up, it will look like this while the output percentage updates:

```
{
    "id": "002edd2a-15f2-4f9d-917b-3f79961d1ad7-u1",
    "status": "IN_PROGRESS",
    "workerId": "mi2kouwfhl1h7a",
    "delayTime": 18,
    "output": "11%"
}
```

When the job completes, it will look like this if the output type is base64 _(truncated the base64 content here with the `...`)_:

```
{
    "id": "002edd2a-15f2-4f9d-917b-3f79961d1ad7-u1",
    "status": "COMPLETED",
    "workerId": "mi2kouwfhl1h7a",
    "delayTime": 18,
    "executionTime": 3003,
    "output": "iVBORw0KGgoAAAANSUhEUgAABAAAAAQACAIAAADwf7zUAAADkHRFWHRwcm9tcHQAeyIzIjogeyJjbGFzc190eXBlIjogIktTYW1wbGVyIiwgImlucHV0cyI6IHsibW9kZWwiOiBbIjQiLCAwXSwg...qa7vr/nitBGCQLPl1XV+lJCCJSMhtegOuGLwTdkWPrpormqYMfcWTvpASy9UxJFk6Cf43JsMMILlOIru+Kunn3X5hjcZxVeKrfFec81r6l1M3qNvflQFUQVBSbor2/wMmbu/Q7F2fpQAAAABJRU5ErkJggg=="
}
```

And if you have S3 enabled, the output type will be an S3 link:

```
{
    "id": "002edd2a-15f2-4f9d-917b-3f79961d1ad7-u1",
    "status": "COMPLETED",
    "workerId": "mi2kouwfhl1h7a",
    "delayTime": 18,
    "executionTime": 3003,
    "output": "https://sketchy-inference-output.s3.us-east-1.amazonaws.com/d62cd4ec-0a60-436d-b87c-bc9271f7a64f-u1.png"
}
```

In case of an error, the completion state will look like this:

```
{
    "id": "002edd2a-15f2-4f9d-917b-3f79961d1ad7-u1",
    "status": "COMPLETED",
    "workerId": "mi2kouwfhl1h7a",
    "delayTime": 18,
    "executionTime": 3003,
    "output": "ERROR"
}
```

Any frontend should be able to handle all these output states.

Runpods rate limits are defined here: https://docs.runpod.io/serverless/endpoints/job-operations#rate-limits
Based on this, you can poll the `/status` endpoint every 1-2 seconds without hitting RunPods rate limits.
