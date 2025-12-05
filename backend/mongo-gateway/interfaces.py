from gridfs import GridFS
from bson import ObjectId

from typing import Optional, BinaryIO, Union, Dict, Any, List
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult
from pymongo.database import Database

import logging

logger = logging.getLogger(__name__)

class FileInfoInterface():

    """
    ==> Surcouche de la gestion pour toutes les informations relatives aux fichiers
    """
    def __init__(self, database: Database, collection_name: str):
        """
        """
        self._collection = database[collection_name]

    def _update_one(
        self,
        criteria: Dict[str, Any],
        update_fields: Dict[str, Any],
        upsert: bool = True
    ) -> UpdateResult:
        try:
            result = self._collection.update_one(
                criteria,
                {'$set': update_fields},
                upsert=upsert
            )
            if result.matched_count == 0 and not upsert:
                raise ValueError("No document matches criteria.")
            return result
        except Exception as e:
            raise RuntimeError(f"Error while updating: {str(e)}")

    
    def update_diarization_infos(
        self,
        sample_level_mean_score: float,
        turn_level_mean_score: float,
        diarization_result: List[Dict[str, Any]],
        job_id: str
    ) -> UpdateResult:
        """
        Met à jour les informations relatives à la diarisation.
        """
        criteria = {'job_id': job_id}
        update_fields = {
            "sample_level_system_score": sample_level_mean_score,
            "turn_level_system_score": turn_level_mean_score,
            "diarization_result": diarization_result,
        }
        return self._update_one(criteria, update_fields)

    def update_human_score(
        self,
        human_score: float,
        filename: str
    ) -> UpdateResult:
        """
        ==> Met à jour le score attribué par l'humine
        """
        criteria = {'filename': filename}
        update_fields = {
            "human_score": human_score
        }
        return self._update_one(criteria, update_fields)

    def update_file_id(
        self,
        file_id: str,
        filename: str
    ) -> UpdateResult:
        """
        ==> Met à jour le file_id d'un fichier
        ==> Utilise si cela fait plus de 48h que PyAnnote a upload le fichier
        """
        criteria = {'filename': filename}
        update_fields = {
            "file_id": file_id
        }
        return self._update_one(criteria, update_fields)

    def update_job_id(
        self,
        job_id: str,
        filename: str
    ) -> UpdateResult:
        criteria = {"filename": filename}
        update_fields = {
            "job_id": job_id
        }
        return self._update_one(criteria, update_fields)

    def create_data(
        self,
        file_id: str,
        storage_type: str,
        filename: str,
        gridfs_id: Union[str, ObjectId]
    ) -> InsertOneResult:
        """
        ==> Ajoute une donnée à la bd
        """
        data = {
            "file_id": file_id,
            "storage_type": storage_type,
            "filename": filename,
            "gridfs_id": gridfs_id
        }
        try:
            result = self._collection.insert_one(data)
            return result
        except Exception as e:
            raise RuntimeError(f"Error while inserting the document: {str(e)}")

    def get_file_id(self, filename: str) -> str:
        """
        Récupère le champ `file_id` d'un document MongoDB en fonction du `filename`.
    
        Args:
            filename (str): Nom du fichier à rechercher.
    
        Returns:
            str: Le `file_id` correspondant.
    
        Raises:
            ValueError: Si le fichier n'est pas trouvé.
            PyMongoError: En cas d'erreur de connexion ou de requête.
        """
        try:
            document = self._collection.find_one(
                {"filename": filename},
                {"file_id": 1, "_id": 0}
            )
        
            if not document:
                raise ValueError(f"Aucun document trouvé pour le fichier '{filename}'.")
        
            return document["file_id"]
        
        except Exception as e:
            raise RuntimeError(f"Erreur MongoDB lors de la recherche: {str(e)}")

class GridfsStorageInterface():
    """
    Interface pour la gestion des fichiers audio dans GridFS.
    Permet l'ajout, la récupération et la suppression de fichiers audio.
    """
    
    def __init__(self, database: Database, collection_name: str):
        """
        Initialise l'interface GridFS pour une collection donnée.

        Args:
            database: Instance de la base de données MongoDB.
            collection_name: Nom de la collection GridFS.
        """
        self._fs = GridFS(database, collection=collection_name)

    def register_audio(
        self,
        data: Union[BinaryIO, bytes],
        filename: str,
        content_type: str = "audio/wav"
    ) -> ObjectId:
        """
        Enregistre un fichier audio dans GridFS.

        Args:
            data: Objet fichier binaire ou bytes du fichier audio.
            filename: Nom du fichier à enregistrer.
            content_type: Type MIME du fichier (par défaut: "audio/wav").

        Returns:
            ObjectId: L'identifiant GridFS du fichier enregistré.

        Raises:
            ValueError: Si le fichier ne peut pas être lu ou est vide.
            RuntimeError: En cas d'erreur lors de l'enregistrement.
        """
        try:
            file_id = self._fs.put(data, filename=filename, contentType=content_type)
            logger.info(f"File {filename} registered with the ID {file_id}")
            return file_id
        except Exception as e:
            logger.error(f"Error while registering the file {filename}: {str(e)}")
            raise RuntimeError(f"Impossible to register the file: {str(e)}")

    def return_audio_byte(self, gridfs_id: Union[str, ObjectId]) -> bytes:
        """
        Récupère un fichier audio sous forme de bytes depuis GridFS.

        Args:
            gridfs_id: ID GridFS du fichier à récupérer.

        Returns:
            bytes: Contenu binaire du fichier audio.

        Raises:
            ValueError: Si l'ID est invalide ou le fichier introuvable.
            RuntimeError: En cas d'erreur lors de la lecture.
        """
        try:
            if isinstance(gridfs_id, str):
                gridfs_id = ObjectId(gridfs_id)
            audio_file = self._fs.get(gridfs_id)
            return audio_file.read()
        except Exception as e:
            logger.error(f"Error wile getting file {gridfs_id}: {str(e)}")
            raise ValueError(f"Impossible to get the file: {str(e)}")
