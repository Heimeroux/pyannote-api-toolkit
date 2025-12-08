import os
import uvicorn
import requests
import logging
import sys
from pymongo import MongoClient
from fastapi import FastAPI, UploadFile, Form, File, status, Query, Body
from fastapi import HTTPException, Response
from interfaces import FileInfoInterface, GridfsStorageInterface
from typing import Dict, List, Any, Union

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
app = FastAPI()

mongo_uri = os.getenv("MONGO_URI")
mongo_database = os.getenv("MONGO_DATABASE")

if not all([mongo_uri, mongo_database]):
    logger.error("Missing required environment variables.")
    sys.exit(1)

client = MongoClient(mongo_uri)
file_infos = FileInfoInterface(client[mongo_database], "file_infos")
audio_storage = GridfsStorageInterface(client[mongo_database], "audio_storage")

@app.post("/files/register")
async def register_and_add_file(
    file: UploadFile = File(...),
    filename: str = Form(...),
    content_type: str = Form(...),
    file_id: str = Form(...),
    storage_type: str = Form(...),
    nb_speakers: int = Form(...)
) -> Dict[str, str]:
    """
    Registers an audio file and adds its metadata to the database.
    Args:
        file: Audio file to register.
        filename: Name of the file.
        content_type: Content type of the file.
        file_id: Unique identifier of the file.
        storage_type: Storage type.
        nb_speakers: Number of speakers in the audio file.
    Returns:
        Dict[str, str]: Status of the operation.
    Raises:
        HTTPException: In case of validation or registration error.
    """
    try:
        # Read file content
        file_data = await file.read()
        if not file_data:
            raise ValueError("The file is empty.")
        # Check uniqueness of the filename
        audio_storage.check_filename_not_registered(filename)
        # Register the audio file
        gridfs_id = audio_storage.register_audio(
            file_data,
            filename,
            content_type,
        )
        # Insert metadata
        insert_result = file_infos.create_data(
            file_id,
            storage_type,
            filename,
            gridfs_id,
            nb_speakers,
        )
        logger.info(
            f"File '{filename}' registered successfully. "
            f"gridfs_id: {gridfs_id}, inserted_id: {insert_result.inserted_id}"
        )
        return {"status": "success"}
    except ValueError as validation_error:
        logger.error(f"Validation error: {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error during registration: {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error: {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/diarization/info")
def get_infos_for_diarization(
    filename: str = Query(..., min_length=1, description="File name (e.g., audio1.mp3)")
) -> Dict[str, Union[str, int]]:
    """
    Retrieves the necessary information for diarization of an audio file.
    Args:
        filename: Name of the audio file to retrieve information for.
    Returns:
        Dict[str, Union[str, int]]:
            - status: Request status ("success" or "error").
            - file_id: Unique identifier of the file.
            - nb_speakers: Number of speakers in the file.
    Raises:
        HTTPException:
            - 400 Bad Request if the file is not found or the name is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        file_id, nb_speakers = file_infos.get_infos_for_diarization(filename)
        logger.info(
            f"Diarization information retrieved for file '{filename}': "
            f"file_id={file_id}, nb_speakers={nb_speakers}"
        )
        return {
            "status": "success",
            "file_id": file_id,
            "nb_speakers": nb_speakers,
        }
    except ValueError as validation_error:
        logger.error(f"Validation error for file '{filename}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving information for '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for file '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.post("/files/job-id")
def update_job_id(
    filename: str = Body(..., embed=True, min_length=1, description="Name of the file sent to diarization"),
    job_id: str = Body(..., embed=True, min_length=1, description="Job ID of the diarization process")
) -> Dict[str, str]:
    """
    Updates the job identifier for a given file.
    Args:
        filename: Name of the file to update the job identifier for.
        job_id: Job identifier of the diarization process to associate with the file.
    Returns:
        Dict[str, str]:
            - status: Request status ("success").
            - message: Confirmation message.
    Raises:
        HTTPException:
            - 400 Bad Request if the file or job_id is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        update_result = file_infos.update_job_id(job_id, filename)
        logger.info(
            f"Job ID '{job_id}' successfully associated with file '{filename}'."
        )
        return {
            "status": "success",
            "message": f"Job ID '{job_id}' updated for file '{filename}'."
        }
    except ValueError as validation_error:
        logger.error(f"Validation error for file '{filename}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error updating job ID for '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for file '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.post("/diarization/results")
async def update_diarization_result(
    job_id: str = Body(
        ...,
        embed=True,
        min_length=1,
        description="Identifier of the diarization job to update"
    ),
    diarization: List[Dict[str, Any]] = Body(
        ...,
        embed=True,
        default_factory=list,
        description="Diarization result (list of segments with speakers and timestamps)"
    ),
    sample_level_mean_score: float = Body(
        ...,
        embed=True,
        ge=0,
        le=100,
        description="Average confidence score (0-100) across all samples"
    ),
    sample_level_confidences: Dict[str, Union[List[int], float]] = Body(
        ...,
        embed=True,
        description="Confidences per sample (system output for each audio segment)"
    )
) -> Dict[str, str]:
    """
    Updates the diarization results for a given job.
    Args:
        job_id: Identifier of the diarization job.
        diarization: Diarization result (segments with speakers and timestamps).
        sample_level_mean_score: Average confidence score (0-100) across all samples.
        sample_level_confidences: Details of confidences per sample.
    Returns:
        Dict[str, str]:
            - status: Request status ("success").
            - message: Confirmation message.
    Raises:
        HTTPException:
            - 400 Bad Request if the data is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        update_result = file_infos.update_diarization_infos(
            sample_level_mean_score,
            diarization,
            job_id,
            sample_level_confidences
        )
        logger.info(
            f"Diarization results updated successfully for job '{job_id}'."
        )
        return {
            "status": "success",
            "message": f"Diarization results and scores updated for job '{job_id}'."
        }
    except ValueError as validation_error:
        logger.error(f"Validation error for job '{job_id}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error updating results for job '{job_id}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for job '{job_id}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/diarization/result")
async def get_diarization_result(
    filename: str = Query(
        ...,
        min_length=1,
        description="Name of the audio file (e.g., audio1.mp3)"
    )
) -> Dict[str, Any]:
    """
    Retrieves the diarization results for a given file.
    Args:
        filename: Name of the audio file to retrieve diarization results for.
    Returns:
        Dict[str, Any]:
            - status: Request status ("success").
            - diarization: Diarization result (list of segments with speakers and timestamps).
    Raises:
        HTTPException:
            - 400 Bad Request if the file name is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        diarization = file_infos.get_diarization_result(filename)
        logger.info(
            f"Diarization results retrieved successfully for file '{filename}'."
        )
        return {
            "status": "success",
            "diarization": diarization
        }
    except ValueError as validation_error:
        logger.error(f"Validation error for file '{filename}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving results for '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for file '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/documents/count")
async def get_documents_count() -> Dict[str, Union[str, int]]:
    """
    Retrieves the total number of registered documents.
    Returns:
        Dict[str, Union[str, int]]:
            - status: Request status ("success").
            - nb_of_docs: Total number of documents.
    Raises:
        HTTPException:
            - 500 Internal Server Error in case of internal error.
    """
    try:
        nb_of_docs = file_infos.get_number_of_documents()
        logger.info(f"Total number of documents retrieved successfully: {nb_of_docs}.")
        return {
            "status": "success",
            "nb_of_docs": nb_of_docs
        }
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving number of documents: {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error retrieving number of documents: {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/filenames")
async def get_all_filenames() -> Dict[str, Union[str, List[str]]]:
    """
    Retrieves the list of all registered file names.
    Returns:
        Dict[str, Union[str, List[str]]]:
            - status: Request status ("success").
            - filenames: List of file names.
    Raises:
        HTTPException:
            - 500 Internal Server Error in case of internal error.
    """
    try:
        filenames = file_infos.get_all_filenames()
        logger.info(f"List of file names retrieved successfully.")
        return {
            "status": "success",
            "filenames": filenames
        }
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving file names: {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error retrieving file names: {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.post("/scores/human")
async def update_human_score(
    human_score: int = Body(
        ...,
        embed=True,
        ge=0,
        le=100,
        description="Score assigned by human evaluation (between 0 and 100)"
    ),
    filename: str = Body(
        ...,
        embed=True,
        min_length=1,
        description="Name of the file to update the human score for"
    )
) -> Dict[str, str]:
    """
    Updates the human score for a given file.
    Args:
        human_score: Score assigned by human evaluation (0-100).
        filename: Name of the file to update.
    Returns:
        Dict[str, str]:
            - status: Request status ("success").
            - message: Confirmation message.
    Raises:
        HTTPException:
            - 400 Bad Request if the data is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        update_result = file_infos.update_human_score(
            human_score,
            filename
        )
        logger.info(
            f"Human score updated successfully for file '{filename}' (score: {human_score})."
        )
        return {
            "status": "success",
            "message": f"Human score ({human_score}) updated for file '{filename}'."
        }
    except ValueError as validation_error:
        logger.error(f"Validation error for file '{filename}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error updating human score for '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for file '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/audio/bytes")
async def get_audio_bytes(
    filename: str = Query(
        ...,
        min_length=1,
        description="Name of the audio file to retrieve (e.g., audio1.mp3)"
    )
) -> Response:
    """
    Retrieves the audio bytes of a given file.
    Args:
        filename: Name of the audio file to retrieve binary data for.
    Returns:
        Response:
            - Binary content of the audio file.
            - Appropriate MIME type.
            - Header for download or inline display.
    Raises:
        HTTPException:
            - 500 Internal Server Error in case of internal error.
    """
    try:
        gridfs_id = file_infos.get_gridfs_id(filename)
        audio_bytes, content_type = audio_storage.return_audio_byte(gridfs_id)
        logger.info(
            f"Audio bytes retrieved successfully for file '{filename}' (gridfs_id: {gridfs_id})."
        )
        return Response(
            content=audio_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving audio bytes for '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error retrieving audio bytes for '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.post("/delete")
async def delete_file(
    filename: str = Body(
        ...,
        embed=True,
        min_length=1,
        description="Name of the file to delete (e.g., audio1.mp3)"
    )
) -> Dict[str, str]:
    """
    Deletes a file and its associated metadata.
    Args:
        filename: Name of the file to delete.
    Returns:
        Dict[str, str]:
            - status: Request status ("success").
            - message: Confirmation message of deletion.
    Raises:
        HTTPException:
            - 400 Bad Request if the file name is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        audio_storage.delete(filename)
        file_infos.delete(filename)
        logger.info(f"File '{filename}' deleted successfully.")
        return {
            "status": "success",
            "message": f"File '{filename}' has been deleted successfully."
        }
    except ValueError as validation_error:
        logger.error(f"Validation error while deleting file '{filename}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error deleting file '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error while deleting file '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/filenames/by-mean-scores")
async def get_filenames_by_mean_scores(
    human_score_min: int = Query(
        ..., ge=0, le=100,
        description="Minimum human score (0-100)"
    ),
    human_score_max: int = Query(
        ..., ge=0, le=100,
        description="Maximum human score (0-100)"
    ),
    system_score_min: int = Query(
        ..., ge=0, le=100,
        description="Minimum sample mean score (0-100)"
    ),
    system_score_max: int = Query(
        ..., ge=0, le=100,
        description="Maximum sample mean score (0-100)"
    )
) -> Dict[str, Union[str, List[Dict[str, Union[str, float, int]]]]]:
    """
    Retrieves file names filtered by human score ranges and sample mean scores.
    Args:
        human_score_min: Minimum human score.
        human_score_max: Maximum human score.
        system_score_min: Minimum sample mean score.
        system_score_max: Maximum sample mean score.
    Returns:
        Dict[str, Union[str, List[Dict[str, Union[str, float, int]]]]]:
            - status: Request status ("success").
            - result: List of files matching the score criteria.
    Raises:
        HTTPException:
            - 500 Internal Server Error in case of internal error.
    """
    try:
        result = file_infos.get_filenames_by_mean_scores(
            human_score_min,
            human_score_max,
            system_score_min,
            system_score_max
        )
        logger.info(
            f"Files filtered by scores retrieved successfully "
            f"(human: [{human_score_min}-{human_score_max}], "
            f"sample: [{system_score_min}-{system_score_max}])."
        )
        return {
            "status": "success",
            "result": result
        }
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving files by scores: {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error retrieving files by scores: {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

@app.get("/confidences/sample-level")
async def get_sample_level_confidences(
    filename: str = Query(
        ...,
        min_length=1,
        description="Name of the audio file (e.g., audio1.mp3)"
    )
) -> Dict[str, Any]:
    """
    Retrieves sample-level confidences for a given file.
    Args:
        filename: Name of the audio file to retrieve confidences for.
    Returns:
        Dict[str, Any]:
            - status: Request status ("success").
            - sample_level_confidences: Details of confidences per sample.
    Raises:
        HTTPException:
            - 400 Bad Request if the file name is invalid.
            - 500 Internal Server Error in case of internal error.
    """
    try:
        sample_level_confidences = file_infos.get_sample_level_confidences(filename)
        logger.info(
            f"Sample-level confidences retrieved successfully for file '{filename}'."
        )
        return {
            "status": "success",
            "sample_level_confidences": sample_level_confidences
        }
    except ValueError as validation_error:
        logger.error(f"Validation error for file '{filename}': {validation_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(validation_error),
        )
    except RuntimeError as runtime_error:
        logger.error(f"Error retrieving confidences for '{filename}': {runtime_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(runtime_error),
        )
    except Exception as unexpected_error:
        logger.error(f"Unexpected error for file '{filename}': {unexpected_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5002))
    uvicorn.run(app, host=host, port=port)
