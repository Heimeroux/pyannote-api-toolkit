# Standard library imports
import os
import sys
import logging
from collections import defaultdict
from typing import Optional, Dict, Union, Any, List, Tuple
# Third-party imports
import requests
import uvicorn
import pandas as pd
import numpy as np  # Added as it is often used with pandas
import seaborn as sns
import matplotlib.pyplot as plt
import io
from matplotlib.patches import Patch
# FastAPI imports
from fastapi import (
    FastAPI,
    UploadFile,
    Form,
    File,
    HTTPException,
    status,
    Request,
    Body,
    Query,
    Response,
)
from fastapi.responses import JSONResponse, StreamingResponse

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = FastAPI()

pyannote_wrapper_host = os.getenv("PYANNOTE_WRAPPER_HOST")
pyannote_wrapper_port = os.getenv("PYANNOTE_WRAPPER_PORT")
mongo_gateway_host = os.getenv("MONGO_GATEWAY_HOST")
mongo_gateway_port = os.getenv("MONGO_GATEWAY_PORT")

if not all([pyannote_wrapper_host, pyannote_wrapper_port, mongo_gateway_host, mongo_gateway_port]):
    logger.error("Missing required environment variables.")
    sys.exit(1)

pyannote_wrapper_uri = f"http://{pyannote_wrapper_host}:{pyannote_wrapper_port}"
mongo_gateway_uri = f"http://{mongo_gateway_host}:{mongo_gateway_port}"

def call_external_service(
    url: str,
    method: str = "GET",
    files: Optional[Dict] = None,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
    json: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    is_binary: bool = False,
) -> Union[Dict, str, Tuple[bytes, str]]:
    """
    Call an external service with the specified HTTP method.
    Args:
        url: URL of the external service.
        method: HTTP method ("GET", "POST", "PUT", "DELETE", etc.). Default: "GET".
        files: Files to send (for multipart/form-data).
        data: Form data (for application/x-www-form-urlencoded).
        params: Query parameters (for GET or query string).
        json: JSON data to send in the body.
        headers: Custom headers.
        is_binary: If True, return binary data and Content-Type.
    Returns:
        Union[Dict, str, Tuple[bytes, str]]:
            - Dict: JSON response if available.
            - str: Text response if no JSON.
            - Tuple[bytes, str]: Binary data and Content-Type if is_binary=True.
    Raises:
        HTTPException: In case of HTTP or request error.
        ValueError: If the HTTP method is not supported.
    """
    try:
        method = method.upper()
        # Select HTTP method
        if method == "GET":
            response = requests.get(url, params=params, headers=headers)
        elif method == "POST":
            response = requests.post(url, files=files, data=data, json=json, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        response.raise_for_status()  # Raise an exception for HTTP error codes
        # Process response
        if is_binary:
            content_type = response.headers.get("Content-Type")
            return response.content, content_type
        else:
            if response.content:
                return response.json()
            return {"status": "success", "message": "Request processed successfully"}
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error ({e.response.status_code}): {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"External service error: {e.response.text}"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection error to external service: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/files/upload")
async def upload_file(
    storage_type: str = Form(..., min_length=1, description="Storage type (e.g., 'local', 'cloud')"),
    filename: str = Form(..., min_length=1, description="File name (e.g., audio1.mp3)"),
    file_id: str = Form(..., min_length=1, description="Unique file identifier"),
    content_type: str = Form(..., min_length=1, description="MIME type of the file (e.g., 'audio/mpeg')"),
    file: UploadFile = File(..., description="Audio file to upload"),
    nb_speakers: int = Form(..., ge=1, le=10, description="Number of speakers (1-10)")
) -> JSONResponse:
    """
    Upload an audio file to PyAnnote and save it to the local database.
    Args:
        storage_type: File storage type.
        filename: File name.
        file_id: Unique file identifier.
        content_type: MIME type of the file.
        file: Audio file to upload.
        nb_speakers: Number of speakers in the recording.
    Returns:
        JSONResponse: JSON response with status and message.
    Raises:
        HTTPException: In case of upload or save error.
    """
    try:
        # Read file
        audio_data = await file.read()
        # Prepare data for PyAnnote
        files = {'file': (filename, audio_data, content_type)}
        pyannote_data = {
            "filename": filename,
            "file_id": file_id
        }
        # Upload to PyAnnote
        pyannote_response = call_external_service(
            url=f"{pyannote_wrapper_uri}/files/upload",
            method="POST",
            files=files,
            data=pyannote_data
        )
        logger.info(f"PyAnnote response for file '{filename}': {pyannote_response}")
        # Prepare data for MongoDB
        mongo_data = {
            "filename": filename,
            "file_id": file_id,
            "storage_type": storage_type,
            "content_type": content_type,
            "nb_speakers": nb_speakers
        }
        # Save to MongoDB
        mongo_response = call_external_service(
            url=f"{mongo_gateway_uri}/files/register",
            method="POST",
            files=files,
            data=mongo_data
        )
        logger.info(f"MongoDB response for file '{filename}': {mongo_response}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"File '{filename}' successfully uploaded to PyAnnote and saved locally."
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while uploading file '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Upload error",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while uploading file '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.post("/diarization/jobs")
async def start_diarization_process(request: Request) -> JSONResponse:
    """
    Start the diarization process for a given audio file.
    Args:
        request: HTTP request containing JSON data with the file name.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - message: Confirmation or error message.
            - job_id: Diarization job identifier (on success).
    Raises:
        HTTPException: In case of error while retrieving information or starting diarization.
    """
    try:
        # Retrieve request data
        request_data = await request.json()
        filename = request_data.get("filename")
        if not filename:
            raise ValueError("File name is required.")
        # 1. Retrieve file information from MongoDB
        mongo_response = call_external_service(
            url=f"{mongo_gateway_uri}/diarization/info",
            method="GET",
            params={"filename": filename}
        )
        logger.info(f"Information retrieved from MongoDB for '{filename}': {mongo_response}")
        file_id = mongo_response["file_id"]
        nb_speakers = mongo_response["nb_speakers"]
        # 2. Start diarization job via PyAnnote
        diarization_response = call_external_service(
            url=f"{pyannote_wrapper_uri}/diarization/jobs",
            method="POST",
            json={
                "file_id": file_id,
                "nb_speakers": nb_speakers
            }
        )
        logger.info(f"Diarization job created for '{filename}' (file_id: {file_id}): {diarization_response}")
        job_id = diarization_response["job_id"]
        # 3. Update job_id in MongoDB
        update_response = call_external_service(
            url=f"{mongo_gateway_uri}/files/job-id",
            method="POST",
            json={
                "filename": filename,
                "job_id": job_id
            }
        )
        logger.info(f"Job ID updated in MongoDB for '{filename}': {update_response}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"Diarization successfully started for '{filename}'.",
                "job_id": job_id
            }
        )
    except ValueError as validation_error:
        logger.error(f"Validation error: {str(validation_error)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": str(validation_error),
                "details": "Invalid input data."
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error: {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error processing request.",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error: {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error.",
                "details": str(unexpected_error)
            }
        )

@app.post("/diarization/results")
async def update_diarization_result(
    job_id: str = Body(
        ..., embed=True, min_length=1,
        description="Diarization job identifier (e.g., 'job123')"
    ),
    diarization: List[Dict[str, Any]] = Body(
        ..., embed=True, default_factory=list,
        description="Diarization results (list of segments with speakers and timestamps)"
    ),
    sample_level_mean_score: float = Body(
        ..., embed=True, ge=0, le=100,
        description="Average confidence score (0-100) across all samples"
    ),
    sample_level_confidences: Dict[str, Union[List[float], float]] = Body(
        ..., embed=True,
        description="Confidences per sample (system output for each audio segment)"
    )
) -> JSONResponse:
    """
    Update diarization results for a given job.
    Args:
        job_id: Diarization job identifier.
        diarization: Diarization result (segments with speakers and timestamps).
        sample_level_mean_score: Average confidence score (0-100) across all samples.
        sample_level_confidences: Details of confidences per sample.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - message: Confirmation or error message.
    Raises:
        HTTPException: In case of error while updating results.
    """
    try:
        # Prepare data for the request
        data = {
            "job_id": job_id,
            "diarization": diarization,
            "sample_level_mean_score": sample_level_mean_score,
            "sample_level_confidences": sample_level_confidences
        }
        # Call external service
        response = call_external_service(
            url=f"{mongo_gateway_uri}/diarization/results",
            method="POST",
            json=data
        )
        logger.info(f"Diarization results successfully updated for job '{job_id}'.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"Diarization results for job '{job_id}' updated successfully."
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while updating results for '{job_id}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error updating diarization results.",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while updating results for '{job_id}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error.",
                "details": str(unexpected_error)
            }
        )

@app.get("/visualization/diarization")
async def get_diarization_plot(
    filename: str = Query(
        ..., min_length=1,
        description="Audio file name (e.g., audio1.mp3)"
    )
) -> Response:
    """
    Generate an SVG plot of the diarization timeline for a given file.
    Args:
        filename: Name of the audio file to visualize diarization.
    Returns:
        Response: SVG image of the diarization plot.
    Raises:
        HTTPException: In case of error while retrieving data.
    """
    try:
        # Retrieve diarization results
        response = call_external_service(
            url=f"{mongo_gateway_uri}/diarization/result",
            method="GET",
            params={"filename": filename}
        )
        logger.info(f"Diarization results retrieved for '{filename}'.")
        diarization_data = response["diarization"]
        if not diarization_data:
            raise ValueError(f"No diarization results found for '{filename}'.")
        # Prepare data for the plot
        df = pd.DataFrame(diarization_data)
        speakers = df["speaker"].unique()
        y_positions = {spk: 0.5 * (i + 1) for i, spk in enumerate(speakers)}
        palette = sns.color_palette("husl", n_colors=len(speakers))
        overlap_color = "red"
        # Detect overlaps
        speaker_segments = defaultdict(list)
        for _, row in df.iterrows():
            speaker_segments[row["speaker"]].append((row["start"], row["end"]))
        # Create events to detect overlaps
        events = []
        for segments in speaker_segments.values():
            for start, end in segments:
                events.append((start, "start"))
                events.append((end, "end"))
        events.sort()
        overlap_intervals = []
        current_overlaps = 0
        for i in range(len(events) - 1):
            current_overlaps += 1 if events[i][1] == "start" else -1
            if current_overlaps > 1:
                overlap_start = events[i][0]
                overlap_end = events[i + 1][0]
                overlap_intervals.append((overlap_start, overlap_end))
        # Merge overlap intervals
        if overlap_intervals:
            overlap_intervals.sort()
            merged_overlaps = []
            current_start, current_end = overlap_intervals[0]
            for start, end in overlap_intervals[1:]:
                if start <= current_end:
                    current_end = max(current_end, end)
                else:
                    merged_overlaps.append((current_start, current_end))
                    current_start, current_end = start, end
            merged_overlaps.append((current_start, current_end))
        else:
            merged_overlaps = []
        # Create the plot
        plt.figure(figsize=(12, 1.5 * len(speakers)))
        for i, speaker in enumerate(speakers):
            for start, end in speaker_segments[speaker]:
                current_pos = start
                segments_to_plot = []
                for overlap_start, overlap_end in merged_overlaps:
                    if overlap_start < end and overlap_end > current_pos:
                        if overlap_start > current_pos:
                            segments_to_plot.append((current_pos, overlap_start, False))
                        segments_to_plot.append((max(current_pos, overlap_start), min(end, overlap_end), True))
                        current_pos = overlap_end
                if current_pos < end:
                    segments_to_plot.append((current_pos, end, False))
                if not segments_to_plot:
                    segments_to_plot.append((start, end, False))
                for seg_start, seg_end, is_overlap in segments_to_plot:
                    color = overlap_color if is_overlap else palette[i]
                    plt.hlines(
                        y=y_positions[speaker],
                        xmin=seg_start,
                        xmax=seg_end,
                        colors=color,
                        lw=10,
                    )
        # Configure axes and legends
        plt.yticks(
            ticks=[y_positions[s] for s in speakers],
            labels=speakers
        )
        plt.ylim(0.25, 0.75 + (len(speakers) - 1) * 0.5)
        plt.xlabel("Time (s)")
        plt.ylabel("Speaker")
        plt.title(f"Timeline of the speech segments for '{filename}'\n(overlaps in red)")
        plt.grid(axis="x", linestyle="--", alpha=0.7)
        # Legend
        legend_elements = [Patch(facecolor=palette[i], label=speaker) for i, speaker in enumerate(speakers)]
        legend_elements.append(Patch(facecolor=overlap_color, label="Overlapping"))
        plt.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        # Export as SVG
        svg_buffer = io.StringIO()
        plt.savefig(svg_buffer, format="svg", bbox_inches="tight")
        svg_content = svg_buffer.getvalue()
        plt.close()
        return Response(content=svg_content, media_type="image/svg+xml")
    except HTTPException as http_error:
        logger.error(f"HTTP error for '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving data",
                "details": str(http_error.detail)
            }
        )
    except ValueError as validation_error:
        logger.error(f"Validation error for '{filename}': {str(validation_error)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": "error",
                "message": str(validation_error),
                "details": "Invalid or missing data"
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.get("/documents/count")
async def get_documents_count() -> JSONResponse:
    """
    Retrieve the total number of registered documents.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - nb_of_docs: Total number of documents (on success).
            - message: Confirmation or error message.
            - details: Additional details (on error).
    Raises:
        HTTPException: In case of error while retrieving data.
    """
    try:
        # Call external service to get the number of documents
        response = call_external_service(
            url=f"{mongo_gateway_uri}/documents/count",
            method="GET"
        )
        nb_of_docs = response["nb_of_docs"]
        logger.info(f"Number of documents retrieved successfully: {nb_of_docs}.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "nb_of_docs": nb_of_docs,
                "message": f"Number of documents retrieved: {nb_of_docs}."
            }
        )
    except KeyError as key_error:
        logger.error(f"Missing key in response: {str(key_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Unexpected response format",
                "details": f"Missing key: {str(key_error)}"
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error: {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving number of documents",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error: {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.get("/filenames")
async def get_all_filenames() -> JSONResponse:
    """
    Retrieve a list of all registered file names.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - filenames: List of file names (on success).
            - message: Confirmation or error message.
            - details: Additional details (on error).
    Raises:
        HTTPException: In case of error while retrieving data.
    """
    try:
        # Call external service to get the list of files
        response = call_external_service(
            url=f"{mongo_gateway_uri}/filenames",
            method="GET"
        )
        filenames = response["filenames"]
        logger.info(f"List of {len(filenames)} files retrieved successfully.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "filenames": filenames,
                "message": f"{len(filenames)} file names retrieved successfully."
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while retrieving file names: {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving file names",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while retrieving file names: {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.post("/scores/human")
async def update_human_score(
    human_score: int = Body(
        ..., embed=True, ge=0, le=100,
        description="Human evaluation score (0-100)"
    ),
    filename: str = Body(
        ..., embed=True, min_length=1,
        description="Name of the file to update (e.g., audio1.mp3)"
    )
) -> JSONResponse:
    """
    Update the human score for a given file.
    Args:
        human_score: Score assigned by human evaluation (between 0 and 100).
        filename: Name of the file whose score should be updated.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - message: Confirmation or error message.
            - details: Additional details (on error).
    Raises:
        HTTPException: In case of error while updating the score.
    """
    try:
        data = {
            "human_score": human_score,
            "filename": filename
        }
        # Call external service to update the human score
        response = call_external_service(
            url=f"{mongo_gateway_uri}/scores/human",
            method="POST",
            json=data
        )
        logger.info(f"Human score ({human_score}) updated successfully for file '{filename}'.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"Human score ({human_score}) updated successfully for '{filename}'."
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while updating score for '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error updating human score",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while updating score for '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.get("/audio/bytes")
async def get_audio_bytes(
    filename: str = Query(
        ..., min_length=1,
        description="Name of the audio file to retrieve (e.g., audio1.mp3)"
    )
) -> Response:
    """
    Retrieve the audio bytes of a given file.
    Args:
        filename: Name of the audio file whose binary data should be retrieved.
    Returns:
        Response: HTTP response containing the audio bytes with the correct MIME type.
    Raises:
        HTTPException: In case of error while retrieving audio data.
    """
    try:
        # Retrieve audio bytes from external service
        audio_bytes, content_type = call_external_service(
            url=f"{mongo_gateway_uri}/audio/bytes",
            method="GET",
            params={"filename": filename},
            is_binary=True
        )
        logger.info(
            f"Audio bytes retrieved successfully for '{filename}' "
            f"(Type: {content_type}, Size: {len(audio_bytes)} bytes)."
        )
        # Return a response with audio bytes and correct MIME type
        return Response(
            content=audio_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=\"{filename}\"",
                "Content-Length": str(len(audio_bytes))
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while retrieving '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving audio data",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while retrieving '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.post("/delete")
async def delete_file(
    filename: str = Body(
        ..., embed=True, min_length=1,
        description="Name of the file to delete (e.g., audio1.mp3)"
    )
) -> JSONResponse:
    """
    Delete a file and its associated metadata.
    Args:
        filename: Name of the file to delete.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - message: Confirmation or error message.
            - details: Additional details (on error).
    Raises:
        HTTPException: In case of error while deleting.
    """
    try:
        # Call external service to delete the file
        response = call_external_service(
            url=f"{mongo_gateway_uri}/delete",
            method="POST",
            json={"filename": filename}
        )
        logger.info(f"File '{filename}' deleted successfully.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": f"File '{filename}' deleted successfully."
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while deleting '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error deleting file",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while deleting '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.get("/filenames/by-mean-scores")
async def get_files_by_mean_scores(
    human_score_min: int = Query(
        ..., ge=0, le=100,
        description="Minimum human score (0-100)"
    ),
    human_score_max: int = Query(
        ..., ge=0, le=100,
        description="Maximum human score (0-100)"
    ),
    sample_score_min: int = Query(
        ..., ge=0, le=100,
        description="Minimum sample mean score (0-100)"
    ),
    sample_score_max: int = Query(
        ..., ge=0, le=100,
        description="Maximum sample mean score (0-100)"
    )
) -> JSONResponse:
    """
    Retrieve files filtered by human score ranges and sample mean scores.
    Args:
        human_score_min: Minimum human score.
        human_score_max: Maximum human score.
        sample_score_min: Minimum sample mean score.
        sample_score_max: Maximum sample mean score.
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - result: List of files matching the score criteria.
            - message: Confirmation or error message.
            - count: Number of files returned (on success).
    Raises:
        HTTPException: In case of error while retrieving data.
    """
    try:
        params = {
            "human_score_min": human_score_min,
            "human_score_max": human_score_max,
            "system_score_min": sample_score_min,
            "system_score_max": sample_score_max
        }
        # Call external service to get filtered files
        response = call_external_service(
            url=f"{mongo_gateway_uri}/filenames/by-mean-scores",
            method="GET",
            params=params
        )
        files = response["result"]
        logger.info(f"{len(files)} files retrieved successfully for scores: "
                   f"human [{human_score_min}-{human_score_max}], "
                   f"samples [{sample_score_min}-{sample_score_max}]."
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "result": files,
                "message": f"{len(files)} files matching score criteria retrieved.",
                "count": len(files)
            }
        )
    except KeyError as key_error:
        logger.error(f"Missing key in response: {str(key_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Unexpected response format",
                "details": f"Missing key: {str(key_error)}"
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error while retrieving files: {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving files by scores",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while retrieving files: {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.get("/confidences/sample-level")
async def get_sample_level_confidences(
    filename: str = Query(
        ..., min_length=1,
        description="Audio file name (e.g., audio1.mp3)"
    ),
    min_score: int = Query(
        0, ge=0, le=100,
        description="Minimum confidence score (0-100)"
    ),
    max_score: int = Query(
        100, ge=0, le=100,
        description="Maximum confidence score (0-100)"
    )
) -> JSONResponse:
    """
    Retrieve sample-level confidences for a given file, filtered by score range.
    Args:
        filename: Audio file name.
        min_score: Minimum confidence score (default: 0).
        max_score: Maximum confidence score (default: 100).
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - result: List of filtered confidence segments.
            - message: Confirmation or error message.
            - count: Number of segments returned (on success).
    Raises:
        HTTPException: In case of error while retrieving data.
    """
    try:
        # Retrieve confidences from external service
        response = call_external_service(
            url=f"{mongo_gateway_uri}/confidences/sample-level",
            method="GET",
            params={"filename": filename}
        )
        logger.info(f"Sample-level confidences retrieved for '{filename}'.")
        sample_level_confidences = response["sample_level_confidences"]
        resolution = sample_level_confidences["resolution"]
        confidences = sample_level_confidences["score"]
        # Filter segments by requested scores
        filtered_segments = []
        for idx, score in enumerate(confidences):
            if min_score <= score <= max_score:
                start = idx * resolution
                end = (idx + 1) * resolution
                filtered_segments.append({
                    "confidence": score,
                    "start": start,
                    "end": end
                })
        logger.info(f"{len(filtered_segments)} filtered segments for '{filename}' "
                   f"(scores between {min_score} and {max_score})."
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "result": filtered_segments,
                "message": f"{len(filtered_segments)} filtered confidence segments retrieved.",
                "count": len(filtered_segments)
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error for '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving confidences",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

@app.get("/confidences/turn-level")
async def get_turn_level_confidences(
    filename: str = Query(
        ..., min_length=1,
        description="Audio file name (e.g., audio1.mp3)"
    ),
    min_score: int = Query(
        0, ge=0, le=100,
        description="Minimum turn-level confidence score (0-100)"
    ),
    max_score: int = Query(
        100, ge=0, le=100,
        description="Maximum turn-level confidence score (0-100)"
    )
) -> JSONResponse:
    """
    Retrieve turn-level confidences for a given file, filtered by score range.
    Args:
        filename: Audio file name.
        min_score: Minimum confidence score (default: 0).
        max_score: Maximum confidence score (default: 100).
    Returns:
        JSONResponse:
            - status: Request status ("success" or "error").
            - result: List of turns filtered by confidence.
            - message: Confirmation or error message.
            - count: Number of turns returned (on success).
    Raises:
        HTTPException: In case of error while retrieving data.
    """
    try:
        # Retrieve diarization results
        response = call_external_service(
            url=f"{mongo_gateway_uri}/diarization/result",
            method="GET",
            params={"filename": filename}
        )
        logger.info(f"Diarization results retrieved for '{filename}'.")
        # Filter turns by requested confidence scores
        filtered_turns = []
        for turn in response["diarization"]:
            speaker = turn["speaker"]
            start = turn["start"]
            end = turn["end"]
            speaker_confidence = turn["confidence"].get(speaker, 0)
            if min_score <= speaker_confidence <= max_score:
                filtered_turns.append({
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                    "speaker_confidence": speaker_confidence
                })
        logger.info(f"{len(filtered_turns)} filtered turns for '{filename}' "
                   f"(scores between {min_score} and {max_score})."
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "result": filtered_turns,
                "message": f"{len(filtered_turns)} filtered turns retrieved.",
                "count": len(filtered_turns)
            }
        )
    except HTTPException as http_error:
        logger.error(f"HTTP error for '{filename}': {http_error.detail}")
        return JSONResponse(
            status_code=http_error.status_code,
            content={
                "status": "error",
                "message": "Error retrieving confidences",
                "details": str(http_error.detail)
            }
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for '{filename}': {str(unexpected_error)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": "Internal server error",
                "details": str(unexpected_error)
            }
        )

if __name__ == '__main__':
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5000))
    uvicorn.run(app, host=host, port=port)

