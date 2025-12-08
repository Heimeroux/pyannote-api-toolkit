import os
import uvicorn
import sys
import pandas as pd
import numpy as np
import requests
import logging
from fastapi import FastAPI, Request, UploadFile, Form, File, status, Body
from fastapi import HTTPException
from typing import Dict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = FastAPI()

api_host = os.getenv("API_HOST")
api_port = os.getenv("API_PORT")
token_pyannote = os.getenv("TOKEN_PYANNOTE")
webhook_uri = os.getenv("WEBHOOK_URI")

if not all([api_host, api_port, token_pyannote, webhook_uri]):
    logger.error("Missing required environment variables.")
    sys.exit(1)

@app.post("/files/upload")
async def upload_file(
    filename: str = Form(..., min_length=1, description="Name of the file to upload"),
    file_id: str = Form(..., min_length=1, description="Unique identifier of the file"),
    file: UploadFile = File(..., description="Audio file to upload")
) -> Dict[str, str]:
    """
    Upload an audio file to the PyAnnote API.
    Args:
        filename: Name of the file to upload.
        file_id: Unique identifier of the file.
        file: Audio file to upload.
    Returns:
        Dict[str, str]:
            - status: Request status ("success").
            - message: Confirmation message.
    Raises:
        HTTPException:
            - 4XX/5XX: In case of error with the PyAnnote API or internal error.
    """
    try:
        # Read file content
        file_data = await file.read()
        # Step 1: Get the pre-signed URL
        presigned_response = requests.post(
            "https://api.pyannote.ai/v1/media/input",
            json={"url": f"media://{file_id}"},
            headers={
                "Authorization": f"Bearer {token_pyannote}",
                "Content-Type": "application/json"
            }
        )
        presigned_response.raise_for_status()
        presigned_url = presigned_response.json()["url"]
        # Step 2: Upload the file to the pre-signed URL
        upload_response = requests.put(
            presigned_url,
            data=file_data
        )
        upload_response.raise_for_status()
        logger.info(f"File '{filename}' (ID: {file_id}) successfully uploaded to PyAnnote.")
        return {
            "status": "success",
            "message": f"File '{filename}' successfully sent to PyAnnote."
        }
    except requests.exceptions.HTTPError as http_error:
        error_detail = http_error.response.json().get("detail", http_error.response.text)
        logger.error(f"Error with PyAnnote API for file '{filename}': {error_detail}")
        raise HTTPException(
            status_code=http_error.response.status_code,
            detail=f"PyAnnote API error: {error_detail}"
        )
    except requests.exceptions.RequestException as request_error:
        logger.error(f"Request error for file '{filename}': {str(request_error)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Connection error to PyAnnote API: {str(request_error)}"
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while uploading file '{filename}': {str(unexpected_error)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

@app.post("/diarization/jobs")
async def start_diarization(
    file_id: str = Body(
        ..., embed=True, min_length=1,
        description="Unique identifier of the audio file to diarize (e.g., 'audio123')"
    ),
    nb_speakers: int = Body(
        ..., embed=True, ge=1, le=100,
        description="Number of speakers in the audio recording (1-100)"
    )
) -> Dict[str, str]:
    """
    Start a diarization job for a given audio file.
    Args:
        file_id: Unique identifier of the audio file.
        nb_speakers: Number of speakers in the recording (between 1 and 100).
    Returns:
        Dict[str, str]:
            - status: Request status ("success").
            - job_id: ID of the created diarization job.
    Raises:
        HTTPException:
            - 4XX/5XX: In case of error with the PyAnnote API or internal error.
    """
    try:
        response = requests.post(
            "https://api.pyannote.ai/v1/diarize",
            json={
                "url": f"media://{file_id}",
                "webhook": webhook_uri,
                "confidence": True,
                "turnLevelConfidence": True,
                "numSpeakers": nb_speakers
            },
            headers={
                "Authorization": f"Bearer {token_pyannote}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        job_id = response.json()["jobId"]
        logger.info(f"Diarization job successfully created for file '{file_id}' (job_id: {job_id}).")
        return {
            "status": "success",
            "job_id": job_id
        }
    except requests.exceptions.HTTPError as http_error:
        error_detail = http_error.response.json().get("detail", http_error.response.text)
        logger.error(f"PyAnnote API error for file '{file_id}': {error_detail}")
        raise HTTPException(
            status_code=http_error.response.status_code,
            detail=f"PyAnnote API error: {error_detail}"
        )
    except requests.exceptions.RequestException as request_error:
        logger.error(f"Connection error to PyAnnote API for '{file_id}': {str(request_error)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"PyAnnote service unavailable: {str(request_error)}"
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while diarizing '{file_id}': {str(unexpected_error)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error."
        )

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5001))
    uvicorn.run(app, host=host, port=port)
