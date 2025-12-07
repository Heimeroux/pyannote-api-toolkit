import requests
import os
import uvicorn
import sys
import logging
import pandas as pd

from fastapi import FastAPI, UploadFile, Form, File, HTTPException, status, Request, Body, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Union, Any, List
from collections import defaultdict

from matplotlib.patches import Patch

from fastapi.responses import Response
import seaborn as sns
import matplotlib.pyplot as plt
import io

pyannote_wrapper_host = os.getenv("PYANNOTE_WRAPPER_HOST")
pyannote_wrapper_port = os.getenv("PYANNOTE_WRAPPER_PORT")
mongo_gateway_host = os.getenv("MONGO_GATEWAY_HOST")
mongo_gateway_port = os.getenv("MONGO_GATEWAY_PORT")

pyannote_wrapper_uri = f"http://{pyannote_wrapper_host}:{pyannote_wrapper_port}"
mongo_gateway_uri = f"http://{mongo_gateway_host}:{mongo_gateway_port}"

app = FastAPI()
logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
    
# create custom handler for INFO msg
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
    
logger.addHandler(stdout_handler)
"""
origins = [
    "http://localhost:8080"
]

# TO DO : To limit properties setted up
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""

def call_external_service(
    url: str,
    method: str,  # Méthode HTTP par défaut : GET
    files: Optional[dict] = None,
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    json: Optional[dict] = None,
    headers: Optional[dict] = None
) -> Union[dict, str]:
    """
    Appelle un service externe avec la méthode HTTP spécifiée.

    Args:
        url: URL du service externe.
        method: Méthode HTTP ("GET", "POST", "PUT", etc.).
        files: Fichiers à envoyer (pour multipart/form-data).
        data: Données de formulaire (pour application/x-www-form-urlencoded).
        params: Paramètres de requête (pour GET ou query string).
        json: Données JSON à envoyer dans le corps.
        headers: En-têtes personnalisés.

    Returns:
        Réponse JSON ou texte du service externe.

    Raises:
        HTTPException: En cas d'erreur HTTP ou de requête.
    """
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, files=files, data=data, json=json, headers=headers)
        else:
            raise ValueError(f"Méthode HTTP non supportée : {method}")

        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        return response.json() if response.content else {"status": "success"}    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Service error: {e.response.text}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Erreur de requête : {str(e)}")

@app.post("/upload")
#async def upload_file(filename: str = Form(...), file: UploadFile = File(...)):
async def upload_file(
    storage_type: str = Form(...),
    filename: str = Form(...),
    file_id: str = Form(...),
    content_type: str = Form(...),
    file: UploadFile = File(...)
) -> Dict[str, str]:
    
    try:
        audio = await file.read()
        files = {'file': (filename, audio, content_type)}

        url_to_use = f'{pyannote_wrapper_uri}/upload_file'

        data = {
            "filename": filename,
            "file_id": file_id
        }
        
        result = call_external_service(
            url_to_use,
            method="POST",
            files=files,
            data=data
        )
        
        logger.info(f"PyAnnote wrapper response: {result}")

        url_to_use = f"{mongo_gateway_uri}/register_add_file"
        data = {
            "filename": filename,
            "file_id": file_id,
            "storage_type": storage_type,
            "content_type": content_type
        }
        
        result = call_external_service(
            url_to_use,
            method="POST",
            files=files,
            data=data
        )
        logger.info(f"Mongo gateway response: {result}")
        
        return {"status": "success", "message": "File successfully registered in PyAnnote and local."}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )

@app.post("/diarise")
async def diarise(request: Request) -> Dict[str, str]:
    
    try:
        data = await request.json()
        filename = data.get("filename")
    
        # Get file_id from mongo db
        # POST ?
        url_to_use = f"{mongo_gateway_uri}/get_file_id"
        data = {
            "filename": filename
        }
        result = call_external_service(url_to_use, method="GET", params=data)
        logger.info(f"Mongo gateway response: {result}")
        file_id = result["file_id"]
    
        # Send file_id for diarisation
        url_to_use = f"{pyannote_wrapper_uri}/diarise"
        data = {
            "file_id": file_id 
        }
        result = call_external_service(url_to_use, method="POST", json=data)
        logger.info(f"PyAnnote wrapper response: {result}")
        job_id = result["job_id"]
    
        # Update file whose filename job_id
        url_to_use = f"{mongo_gateway_uri}/update_job_id"
        data = {
            "filename": filename,
            "job_id": job_id
        }
        result = call_external_service(url_to_use, method="POST", json=data)
        logger.info(f"Mongo gateway response: {result}")
        
        return {"status": "success", "message": "File successfully sent for diarisation on PyAnnote API. MongoDB successfully updated."}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )

@app.post("/update_diarization_result")
async def ask_to_update_diarization_result(
    job_id: str = Body(..., embed=True, min_length=1, description="File ID of the file to ask for diarisation"),
    diarization: List[Dict[str, Any]] = Body(..., embed=True, default_factory=list, description="Diarization result"),
    turn_level_mean_score: float = Body(..., embed=True, ge=0, le=100, description="Mean of the confidences scores over all turn"),
    sample_level_mean_score: float = Body(..., embed=True, ge=0, le=100, description="Mean of the confidences scores over all samples")
) -> Dict[str, str]:
    try:
        url_to_use = f"{mongo_gateway_uri}/update_diarization_result"
        data = {
            "job_id": job_id,
            "diarization": diarization,
            "turn_level_mean_score": turn_level_mean_score,
            "sample_level_mean_score": sample_level_mean_score
        }
        result = call_external_service(url_to_use, method="POST", json=data)
        logger.info(f"Mongo gateway response: {result}")
        
        return {"status": "success", "message": "File infos successfully updated."}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )
        
@app.get("/plot")
async def get_plot(
    filename: str = Query(..., min_length=1, description="Nom du fichier (ex: audio1.mp3)")
):
    # Get diarization result
    try:
        url_to_use = f"{mongo_gateway_uri}/get_diarization_result"
        data = {
            "filename": filename
        }
        result = call_external_service(url_to_use, method="GET", params=data)
        logger.info(f"Successfully got diarization result for file {filename}.")
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )

    logger.info(f"Result: {result}")
    
    df = pd.DataFrame(result["diarization"])

    speakers = df["speaker"].unique()
    y_positions = {spk: 0.5 * (i + 1) for i, spk in enumerate(speakers)}

    plt.figure(figsize=(12, 1.5*len(speakers)))

    palette = sns.color_palette("husl", n_colors=len(speakers))

    overlap_color = "red"

    speaker_segments = defaultdict(list)
    for _, row in df.iterrows():
        speaker_segments[row["speaker"]].append((row["start"], row["end"]))

    # Detect overlap segments
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
            
    # Fusion overlap segments
    if overlap_intervals:
        overlap_intervals.sort()
        merged_overlaps = []
        current_start, current_end = overlap_intervals[0]
        for start, end in overlap_intervals[1:]:
            # TO DO : add example to illustrate
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                merged_overlaps.append((current_start, current_end))
                current_start, current_end = start, end
        merged_overlaps.append((current_start, current_end))
    else:
        merged_overlaps = []

    # Draw segments foreach speaker
    for i, speaker in enumerate(speakers):
        for start, end in speaker_segments[speaker]:
            # Verify if there is overlap
            current_pos = start
            segments_to_plot = []
            for overlap_start, overlap_end in merged_overlaps:
                if overlap_start < end and overlap_end > current_pos:
                    # Add the sub-segment before overlap and indicates there is no overlap
                    if overlap_start > current_pos:
                        segments_to_plot.append((current_pos, overlap_start, False))
                    # Add the overlap sub-segments and indicates there is overlap
                    segments_to_plot.append((max(current_pos, overlap_start), min(end, overlap_end), True))
                    current_pos = overlap_end
            # If all overlaps ended before the end of the segments
            if current_pos < end:
                segments_to_plot.append((current_pos, end, False))
            # If no overlaps add the full segment and indicates there is no overlap
            if not segments_to_plot:
                segments_to_plot.append((start, end, False))

            # Draw each sub-segments
            for seg_start, seg_end, is_overlap in segments_to_plot:
                color = overlap_color if is_overlap else palette[i]
                plt.hlines(
                    y=y_positions[speaker],
                    xmin=seg_start,
                    xmax=seg_end,
                    colors=color,
                    lw=10,
                )

    # Manage axis y positions
    plt.yticks(
        ticks=[y_positions[s] for s in speakers],
        labels=speakers
    )
    plt.ylim(0.25, 0.75 + (len(speakers) - 1)*0.5)

    plt.xlabel("Temps (s)")
    plt.ylabel("Speaker")
    plt.title("Timeline des segments de parole (superpositions en rouge)")
    plt.grid(axis="x", linestyle="--", alpha=0.7)

    # Legend
    legend_elements = [Patch(facecolor=palette[i], label=speaker) for i, speaker in enumerate(speakers)]
    legend_elements.append(Patch(facecolor=overlap_color, label="Overlap"))
    plt.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()

    # Export as SVG
    svg_buffer = io.StringIO()
    plt.savefig(svg_buffer, format="svg", bbox_inches="tight")
    svg_content = svg_buffer.getvalue()
    plt.close()

    return Response(content=svg_content, media_type="image/svg+xml")

@app.get("/get_number_of_documents")
def get_number_of_documents() -> Dict[str, Union[str, int]]:
    try:
        url_to_use = f"{mongo_gateway_uri}/get_number_of_documents"
        result = call_external_service(url_to_use, method="GET")
        logger.info(f"Successfully got number of documents: {result['nb_of_docs']}.")
        return {"status": "success", "nb_of_docs": result["nb_of_docs"]}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )

@app.get("/get_all_filenames")
def get_all_filenames() -> Dict[str, Union[str, List[str]]]:
    try:
        url_to_use = f"{mongo_gateway_uri}/get_all_filenames"
        result = call_external_service(url_to_use, method="GET")
        logger.info(f"Successfully got number of documents: {result['filenames']}.")
        return {"status": "success", "filenames": result["filenames"]}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )
        
@app.post("/update_human_score")
def update_human_score(
    human_score: int = Body(..., embed=True, ge=0, le=100, description="Score from human assessment"),
    filename: str = Body(..., embed=True, min_length=1, description="Name of the file sent to diarisation")
) -> Dict[str, str]:
    try:
        url_to_use = f"{mongo_gateway_uri}/update_human_score"
        data = {
            "human_score": human_score,
            "filename": filename
        }
        result = call_external_service(url_to_use, method="POST", json=data)
        logger.info(f"Mongo gateway response: {result}")
        
        return {"status": "success", "message": "File infos successfully updated."}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )

if __name__ == '__main__':
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5000))
    uvicorn.run(app, host=host, port=port)
