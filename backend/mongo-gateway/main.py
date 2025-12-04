import os
import uvicorn
import requests
import logging

from pymongo import MongoClient
from fastapi import FastAPI, UploadFile, Form, File, status
from fastapi import HTTPException
from interfaces import FileInfoInterface, GridfsStorageInterface
from typing import Dict

mongo_uri = os.getenv("MONGO_URI")
mongo_database = os.getenv("MONGO_DATABASE")

client = MongoClient(mongo_uri)

file_infos = FileInfoInterface(client[mongo_database], "file_infos")
audio_storage = GridfsStorageInterface(client[mongo_database], "audio_storage")

app = FastAPI()
logger = logging.getLogger(__name__)

@app.post("/register_add_file")
async def register_and_add_file(
    file: UploadFile = File(...),
    filename: str = Form(...),
    content_type: str = Form(...),
    file_id: str = Form(...),
    storage_type: str = Form(...)
) -> Dict[str, str]:
    try:
        data = await file.read()
        if not data:
            raise ValueError("Empty file.")

        gridfs_id = audio_storage.register_audio(data, filename, content_type)
        insert_result = file_infos.create_data(file_id, storage_type, filename, gridfs_id)
        logger.info(f"File {filename} registered with gridfs_id: {gridfs_id}, inserted_id: {insert_result.inserted_id}")
        return {"status": "success"}
    except ValueError as ve:
        logger.error(f"Erreur de validation: {str(ve)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except RuntimeError as re:
        logger.error(f"Erreur d'enregistrement: {str(re)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(re))
    except Exception as e:
        logger.error(f"Erreur inattendue: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur interne du serveur")

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5002))
    uvicorn.run(app, host=host, port=port)
