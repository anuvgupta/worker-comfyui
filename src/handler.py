import os
import time
import json
import math
import uuid
import boto3
import base64
import runpod
import signal
import shutil
import asyncio
import requests
import botocore
import threading
import traceback
import websockets
import subprocess

from workflows import get_workflow, get_default_workflow


# Worker Configuration
APP_NAME=os.getenv('APP', 'APP')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'DEVELOPMENT')
PROD = ENVIRONMENT == "PRODUCTION"
DEV = ENVIRONMENT == "DEVELOPMENT"
# System
LOCAL_HOST_IP = "127.0.0.1"
PYTHON_PATH_DEV = os.getenv('PYTHON_PATH_DEV', '/usr/bin/python3')
PYTHON_PATH = "/opt/venv/bin/python" if PROD else PYTHON_PATH_DEV
# Health check mode
HEALTH_CHECK_MODE = os.getenv('HEALTH_CHECK_MODE', 'FALSE') == 'TRUE'
# Network volume config
ENABLE_NETWORK_VOLUME = os.getenv('ENABLE_NETWORK_VOLUME', 'FALSE') == 'TRUE'
MODEL_CACHE_PATH_DEV = os.getenv('MODEL_CACHE_PATH_DEV', '/workspace/models')
MODEL_CACHE_PATH = "/runpod-volume/models" if PROD else MODEL_CACHE_PATH_DEV
# AWS config
ENABLE_S3_UPLOAD = os.getenv('ENABLE_S3_UPLOAD', 'FALSE') == 'TRUE'
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY', '')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY', '')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME', '')
AWS_REGION_DEFAULT = 'us-east-1'
AWS_REGION = os.getenv('AWS_REGION', AWS_REGION_DEFAULT)
S3_CACHE_CONTROL_MAX_AGE = "31536000"  # 1 year cache
# ComfyUI config
COMFYUI_PORT = 3000
COMFYUI_CLIENT_ID = str(uuid.uuid4())
COMFYUI_FILENAME_PREFIX = APP_NAME
COMFYUI_WEB_URL = f"http://{LOCAL_HOST_IP}:{COMFYUI_PORT}"
COMFYUI_WS_URL = f"ws://{LOCAL_HOST_IP}:{COMFYUI_PORT}/ws"
COMFYUI_PATH_DEV = os.getenv('COMFYUI_PATH_DEV', os.path.expanduser("~/comfyui"))
COMFYUI_PATH = "/comfyui" if PROD else COMFYUI_PATH_DEV
COMFYUI_JOB_TIMEOUT_SEC = int(os.getenv("COMFYUI_JOB_TIMEOUT_SEC", "180"))


# Worker memory
comfy_session = None
comfyui_process = None
active_websockets = None
s3_client = None


# utility method for ComfyUI logging
def stream_output(pipe, prefix):
    """
    Stream output from a pipe to stdout with a prefix
    """
    for line in iter(pipe.readline, ''):
        print(f"{prefix}: {line.rstrip()}")


# start managed local ComfyUI instance
def start_comfyui():
    """
    Start ComfyUI if it's not already running
    Returns the process object
    """
    global comfyui_process
    
    # Check if ComfyUI is already running on the specified port
    try:
        print("Checking if ComfyUI instance  is already running before starting new ComfyUI instance")
        response = requests.get(f"{COMFYUI_WEB_URL}/system_stats", timeout=1)
        if response.status_code == 200:
            print(f"ComfyUI instance is already running on port {COMFYUI_PORT}")
            return None
    except requests.exceptions.RequestException:
        pass

    # Start ComfyUI
    try:
        print(f"Starting new ComfyUI instance on port {COMFYUI_PORT}...")
        process = subprocess.Popen(
            [ PYTHON_PATH, "main.py", "--port", str(COMFYUI_PORT), "--listen", "0.0.0.0" ],
            cwd=COMFYUI_PATH,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,  # Makes the process a session leader
            bufsize=1,  # Line buffered
            universal_newlines=True  # Text mode
        )
        comfyui_process = process

        # Start threads to handle output streams
        stdout_thread = threading.Thread(
            target=stream_output, 
            args=(process.stdout, "ComfyUI"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=stream_output, 
            # args=(process.stderr, "ComfyUI Error"),
            args=(process.stderr, "ComfyUI"),
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        print("ComfyUI process started")
        return process
    except Exception as e:
        print(f"ERROR: Failed to start ComfyUI: {str(e)}")
        raise


# stop managed local ComfyUI instance
def stop_comfyui():
    """
    Stop the ComfyUI process if it's running
    """
    global comfyui_process
    if comfyui_process:
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(comfyui_process.pid), signal.SIGTERM)
            comfyui_process = None
            print("ComfyUI process stopped")
        except Exception as e:
            print(f"ERROR: Failed to stop ComfyUI: {str(e)}")
            raise


# wait until local ComfyUI instance is available
def wait_for_comfyui():
    """
    Check if the service is ready to receive requests.
    """
    print("Waiting for ComfyUI")
    while True:
        try:
            print("Checking if ComfyUI is running")
            response = requests.get(f"{COMFYUI_WEB_URL}/system_stats", timeout=120)
            if response.status_code != 200:
                raise RuntimeError(f"ERROR: Got error {response.status_code} from ComfyUI")
            return
        except requests.exceptions.RequestException:
            print("ComfyUI not ready yet. Retrying...")
        except Exception as err:
            print("ERROR Error: ", err)
        time.sleep(0.5)


def link_cached_models():
    print("Linking models from cache")
    # Get types by listing directories in MODEL_CACHE_PATH
    types = [d for d in os.listdir(MODEL_CACHE_PATH) 
             if os.path.isdir(os.path.join(MODEL_CACHE_PATH, d))]
    # Link model types
    for type in types:
        source_path = f"{MODEL_CACHE_PATH}/{type}"
        target_path = f"{COMFYUI_PATH}/models/{type}"
        # Remove existing directory/link if it exists
        if os.path.exists(target_path):
            if os.path.islink(target_path):
                os.unlink(target_path)
            else:
                shutil.rmtree(target_path)
        # Create symbolic link
        os.symlink(source_path, target_path)
        print(f"Linked {type} models into {target_path}")


# setup comfyui http session
def setup_comfyui_session():
    """
    Creates an HTTP request session configured for ComfyUI communication.
    The session is set up with automatic retries for common HTTP server errors.
    """
    global comfy_session
    comfy_session = requests.Session()
    retries = requests.adapters.Retry(total=10, backoff_factor=0.1, status_forcelist=[502, 503, 504])
    comfy_session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retries))


# close comfyui http session
def close_comfyui_session():
    """
    Close HTTP request session for ComfyUI if it exists.
    """
    global comfy_session
    if comfy_session:
        try:
            comfy_session.close()
            print("Closed HTTP session")
        except Exception as e:
            print(f"ERROR: Error while closing HTTP session: {str(e)}")
            raise


# queue new image generation prompt via local ComfyUI instance
def queue_prompt(user_prompt, workflow_data):
    """
    Queue a prompt to ComfyUI and return the prompt ID
    """
    global comfy_session
    try:
        sanitized_prompt = str(user_prompt).encode('unicode_escape').decode('utf-8')
        print(f"Queueing prompt {sanitized_prompt}")

        request_data = {
            "prompt": workflow_data,
            "client_id": COMFYUI_CLIENT_ID
        }
        print("Sending prompt request to ComfyUI local instance")
        response = comfy_session.post(f"{COMFYUI_WEB_URL}/prompt", json=request_data)
        
        response.raise_for_status()
        response_data = response.json()
        
        print(f"ComfyUI response: {response_data}")
        
        if not response_data:
            raise ValueError("ERROR: Empty ComfyUI response")
        if 'prompt_id' not in response_data:
            raise ValueError("ERROR: No prompt_id in ComfyUI response")
        if 'error' in response_data:
            raise RuntimeError(f"ERROR: ComfyUI error: {response_data['error']}")
            
        return response_data['prompt_id']
        
    except Exception as e:
        print(f"ERROR: Error queueing prompt: {str(e)}")
        raise


# connect to S3 via boto client
def get_s3_client():
    """
    Returns a cached boto3 S3 client instance, creating a new one if it doesn't exist.
    """
    global s3_client
    if s3_client:
        print("Already connected to S3")
    else:
        print("Connecting to S3")
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        print("Connected to S3")
    return s3_client


# get path on filesystem of job output image
def get_output_image_path(job_id):
    """
    Constructs and returns the filesystem path where ComfyUI will save the output image for a given job ID.
    """
    return f"{COMFYUI_PATH}/output/{COMFYUI_FILENAME_PREFIX}_{job_id}_00001_.png"


# upload job output image to S3
def upload_image(job_id):
    """
    Uploads the generated image to AWS S3 if bucket is configured, returning the public URL.
    Returns empty string if S3 upload is not enabled or fails.
    """
    if AWS_BUCKET_NAME and AWS_BUCKET_NAME != "":
        image_path = get_output_image_path(job_id)
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"ERROR: Generated image not found at {image_path}")
        print("Getting S3 client")
        s3_client = get_s3_client()
        try:
            filename = f"{job_id}.png"
            print("Uploading image file to S3")
            s3_client.upload_file(
                image_path,
                AWS_BUCKET_NAME,
                filename,
                ExtraArgs={
                    'ContentType': 'image/png',
                    'CacheControl': f"max-age={S3_CACHE_CONTROL_MAX_AGE}",
                }
            )
            url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
            print(f"Uploaded image file to S3 at URL: {url}")
            print(f"Removing image file at path: {image_path}")
            os.remove(image_path)
            return url
        except botocore.exceptions.ClientError as e:
            print(f"ERROR: Error uploading to S3: {str(e)}")
            print("Check if AWS creds are added in env variables, they might be missing")
            raise
        except Exception as e:
            print(f"ERROR: Unexpected error during upload: {str(e)}")
            print("Check if AWS creds are added in env variables, they might be missing")
            raise
    return ""


# get encoded job output image
def get_base64_image(job_id):
    """
    Reads the output image for a given job and returns it as a base64-encoded string.
    Returns empty string if image not found.
    """
    print("Converting image to base64")
    image_path = get_output_image_path(job_id)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"ERROR: Generated image not found at {image_path}")
    
    with open(image_path, 'rb') as image_file:
        # Read the binary image data
        image_binary = image_file.read()
        # Convert to base64 and decode to string (removing b'' prefix)
        base64_string = base64.b64encode(image_binary).decode('utf-8')
        return base64_string
    
    return ""


# update serverless job progress status in Runpod
def update_job(event, progress_percentage):
    """
    Updates the job progress on Runpod with a percentage completion value.
    """
    if event:
        runpod.serverless.progress_update(event, f"{progress_percentage}%")


# close any active ws connections
def close_active_websockets():
    """
    Close any active WebSocket connections.
    """
    global active_websockets
    if active_websockets:
        print("Cleaning up active WebSocket connections")
        for ws in active_websockets.copy():
            try:
                asyncio.create_task(ws.close())
                print("Closed WebSocket connection")
            except Exception as e:
                print(f"ERROR: Error closing WebSocket connection: {str(e)}")
        active_websockets.clear()


# launch a websocket listener for a comfyui job
async def handle_websocket(prompt_id, job_id, job_event, workflow_data):
    """
    Async WebSocket handler to monitor job status
    """
    global active_websockets
    total_nodes = len(workflow_data.keys())
    progress_per_node = float(100 / float(total_nodes))
    nodes_seen = set()
    
    ws_url = f"{COMFYUI_WS_URL}?clientId={COMFYUI_CLIENT_ID}"
    
    async with websockets.connect(ws_url) as websocket:
        if active_websockets == None:
            active_websockets = set()
        active_websockets.add(websocket)
        try:
            while True:
                try:
                    message = await websocket.recv()
                    response = json.loads(message)
                    
                    if "type" not in response or "data" not in response:
                        continue
                        
                    type = response['type']
                    data = response['data']
                    
                    if "prompt_id" not in data or data["prompt_id"] != prompt_id:
                        continue

                    job_progress_percentage = 0
                    
                    if type in ["executing", "progress"]:
                        if "node" in data and data["node"]:
                            node_label = data["node"]
                            nodes_seen.add(node_label)
                            job_progress_percentage = float(100 * (float(len(nodes_seen)) - 1) / float(total_nodes))
                            
                            if 'max' in data and 'value' in data:
                                curr_node_progress = float(data['value'])
                                max_node_progress = float(data['max'])
                                job_progress_percentage += float(progress_per_node * curr_node_progress / max_node_progress)
                                
                            job_progress_percentage = int(math.ceil(job_progress_percentage))
                            print(f"Job {job_id} with prompt {prompt_id} is {job_progress_percentage}% done")
                            update_job(job_event, job_progress_percentage)

                    elif type == "execution_success":
                        job_progress_percentage = 99
                        print(f"ComfyUI generation for job {job_id} completed successfully")
                        print(f"Job {job_id} with prompt {prompt_id} is {job_progress_percentage}% done")
                        update_job(job_event, job_progress_percentage)
                        return

                    elif type == "execution_error":
                        error_msg = data.get("error", "Unknown error occurred")
                        print(f"ERROR: job {job_id} execution failed")
                        print(error_msg)
                        raise RuntimeError(error_msg)

                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    print(f"WebSocket error: {str(e)}")
                    raise
        finally:
            active_websockets.remove(websocket)


# process an image generation job via comfyui
async def process_job(user_prompt, workflow, aspect_ratio, job_id, job_event):
    """
    Processes a single image generation job by starting ComfyUI, queuing the prompt with the specified workflow,
    monitoring execution via WebSocket, and returning either an S3 URL or base64 image data on completion.
    """
    print(f"Starting job {job_id}")
    # Ensure ComfyUI is running
    print("Checking if ComfyUI is running at job start")
    start_comfyui()
    wait_for_comfyui()
    
    # Process the request
    try:

        workflow_data = workflow.load(
            user_prompt,
            aspect_ratio,
            job_id,
            COMFYUI_FILENAME_PREFIX
        )

        prompt_id = queue_prompt(
            user_prompt,
            workflow_data
        )
        
        await asyncio.wait_for(
            handle_websocket(prompt_id, job_id, job_event, workflow_data),
            timeout=COMFYUI_JOB_TIMEOUT_SEC
        )

        result = None
        if ENABLE_S3_UPLOAD:
            image_url = upload_image(
                job_id
            )
            result = image_url
        else:
            base64_image_data =  get_base64_image(
                job_id
            )
            result = base64_image_data

        print(f"Completed job {job_id}")
        return result
            
    except asyncio.TimeoutError:
        raise TimeoutError(f"ERROR: ComfyUI prompt request timed out after {COMFYUI_JOB_TIMEOUT_SEC} seconds")


# main runpod serverless function handler
async def handler(event):
    """
    Async RunPod handler function
    """
    if HEALTH_CHECK_MODE:
        return "OK"
    
    print("Received request for inference")
    print(event)
        
    try:
        if 'id' not in event:
            raise RuntimeError("ERROR: missing 'id' field in runpod handler request")
        job_id = event["id"]

        print(f"Processing Runpod job ID: {job_id}")

        if 'input' not in event:
            raise RuntimeError("ERROR: missing 'input' field in runpod handler request")
        
        if 'prompt' not in event['input']:
            raise RuntimeError("ERROR: missing 'input.prompt' field in runpod handler request")
        prompt = event["input"]["prompt"]

        workflow = get_default_workflow()
        if 'workflow' in event['input']:
            workflow = get_workflow(event["input"]["workflow"])

        aspect_ratio = "1_1"
        if 'aspect_ratio' in event['input']:
            aspect_ratio = event["input"]["aspect_ratio"]
        
        return await process_job(prompt, workflow, aspect_ratio, job_id, event)
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        print(traceback.format_exc())
        return "ERROR"
    

# initialize runpod serverless function
def init_runpod():
    """
    Starts the Runpod serverless handler with the async handler function.
    """
    print("Starting Runpod serverless handler")
    runpod.serverless.start({ "handler": handler })


# initialize comfyui background process
def init_comfyui():
    """
    Initializes a ComfyUI session with retry logic and starts a ComfyUI instance.
    Waits for the instance to be ready before returning.
    """
    print("Initializing ComfyUI instance")
    start_comfyui()
    wait_for_comfyui()
    setup_comfyui_session()
    print("ComfyUI instance is ready")


# main clean up
def cleanup():
    """
    Clean up any background processes & open connections
    """
    stop_comfyui()
    close_comfyui_session()
    close_active_websockets()


# main method
def main():
    """
    Initialize ComfyUI instance (unless in health check mode) and start the Runpod serverless handler.
    Ensures proper cleanup of ComfyUI process and worker memory on exit.
    """
    if not HEALTH_CHECK_MODE:
        print("Starting Runpod in production mode")
        if ENABLE_NETWORK_VOLUME:
            link_cached_models()
        init_comfyui()
    else:
        print("Starting Runpod in health check mode")
    try:
        init_runpod()
    finally:
        cleanup()


# entry point
if __name__ == "__main__":
   main()
