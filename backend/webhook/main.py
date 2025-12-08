import hmac
import hashlib
import logging
import os
import sys
from typing import Any, Dict
import numpy as np
import pandas as pd
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Log configuration
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Application configuration
app = FastAPI()

# Retrieve environment variables
key = os.getenv("PYANNOTEAI_WEBHOOK_SIGNING_SECRET")
api_server_host = os.getenv("API_SERVER_HOST")
api_server_port = os.getenv("API_SERVER_PORT")

if not all([key, api_server_host, api_server_port]):
    logger.error("Missing required environment variables.")
    sys.exit(1)

api_server_uri = f"http://{api_server_host}:{api_server_port}"

def handle_error(logger: logging.Logger, error: Exception, context: str = "") -> None:
    """Centralizes error handling."""
    logger.error(f"{context} Error: {str(error)}")
    raise HTTPException(status_code=500, detail=str(error))

@app.post("/webhook")
async def validate_signature(request: Request) -> JSONResponse:
    """
    Validates the request signature and processes the data if valid.
    """
    try:
        body = await request.body()
        headers = request.headers
        timestamp = headers.get("x-request-timestamp")
        received_signature = headers.get("x-signature")
        if not timestamp or not received_signature:
            logger.error("Missing required headers in webhook endpoint.")
            raise HTTPException(status_code=400, detail="Missing headers")

        signed_content = f"v0:{timestamp}:{body.decode('utf-8')}"
        calculated_signature = hmac.new(
            key=key.encode("utf-8"),
            msg=signed_content.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_signature, received_signature):
            logger.error("Invalid signature in webhook endpoint.")
            raise HTTPException(status_code=403, detail="Invalid signature")

        data = await request.json()
        result = process_result(data)
        return JSONResponse(
            status_code=200,
            content={"status": "received"},
        )
    except Exception as e:
        handle_error(logger, e, "Webhook validation failed")

def process_result(body: Dict[str, Any]) -> None:
    """
    Processes the request result and sends the data to the API server.
    """
    try:
        job_id = body["jobId"]
        diarization = body["output"]["diarization"]
        sample_level_mean_score = np.mean(body["output"]["confidence"]["score"])
        sample_level_confidences = body["output"]["confidence"]

        logger.info(f"Processing job {job_id}.")

        data = {
            "job_id": job_id,
            "diarization": diarization,
            "sample_level_mean_score": sample_level_mean_score,
            "sample_level_confidences": sample_level_confidences,
        }

        url_to_use = f"{api_server_uri}/diarization/results"
        response = requests.post(url_to_use, json=data)
        response.raise_for_status()

        logger.info(f"Diarization result successfully updated for job {job_id}.")
    except Exception as e:
        handle_error(logger, e, "Failed to process diarization result")

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5003))
    uvicorn.run(app, host=host, port=port)
