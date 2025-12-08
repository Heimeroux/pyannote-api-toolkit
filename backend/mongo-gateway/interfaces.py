from gridfs import GridFS
from bson import ObjectId
from typing import Optional, BinaryIO, Union, Dict, Any, List, Tuple
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult
from pymongo.database import Database

class FileInfoInterface:
    """
    Wrapper for managing file-related information in MongoDB.
    """
    def __init__(self, database: Database, collection_name: str) -> None:
        """
        Initialize the interface with the specified MongoDB collection.
        Args:
            database: MongoDB database instance.
            collection_name: Name of the collection to use.
        """
        self._collection = database[collection_name]

    def _update_one(
        self,
        criteria: Dict[str, Any],
        update_fields: Dict[str, Any],
        upsert: bool = True
    ) -> UpdateResult:
        """
        Update a document in the collection.
        Args:
            criteria: Search criteria for the document to update.
            update_fields: Fields to update.
            upsert: If True, create a new document if no document matches the criteria.
        Returns:
            Update result.
        Raises:
            ValueError: If no document matches the criteria and upsert is False.
            RuntimeError: In case of update error.
        """
        try:
            result = self._collection.update_one(
                criteria,
                {"$set": update_fields},
                upsert=upsert
            )
            if result.matched_count == 0 and not upsert:
                raise ValueError("No document matches criteria.")
            return result
        except Exception as e:
            raise RuntimeError(f"Error while trying to update: {str(e)}")

    def update_diarization_infos(
        self,
        sample_level_mean_score: float,
        diarization_result: List[Dict[str, Any]],
        job_id: str,
        sample_level_confidences: Dict[str, Union[List[float], float]]
    ) -> UpdateResult:
        """
        Update diarization information for a given job.
        Args:
            sample_level_mean_score: Mean score at sample level.
            diarization_result: Diarization result.
            job_id: Job identifier.
            sample_level_confidences: Confidences at sample level.
        Returns:
            Update result.
        """
        criteria = {"job_id": job_id}
        update_fields = {
            "sample_level_system_score": sample_level_mean_score,
            "diarization_result": diarization_result,
            "sample_level_confidences": sample_level_confidences
        }
        return self._update_one(criteria, update_fields)

    def update_human_score(self, human_score: float, filename: str) -> UpdateResult:
        """
        Update the human-assigned score for a given file.
        Args:
            human_score: Human-assigned score.
            filename: File name.
        Returns:
            Update result.
        """
        criteria = {"filename": filename}
        update_fields = {"human_score": human_score}
        return self._update_one(criteria, update_fields)

    def update_file_id(self, file_id: str, filename: str) -> UpdateResult:
        """
        Update the file identifier for a given file.
        Args:
            file_id: New file identifier.
            filename: File name.
        Returns:
            Update result.
        """
        criteria = {"filename": filename}
        update_fields = {"file_id": file_id}
        return self._update_one(criteria, update_fields)

    def update_job_id(self, job_id: str, filename: str) -> UpdateResult:
        """
        Update the job identifier for a given file.
        Args:
            job_id: New job identifier.
            filename: File name.
        Returns:
            Update result.
        """
        criteria = {"filename": filename}
        update_fields = {"job_id": job_id}
        return self._update_one(criteria, update_fields)

    def create_data(
        self,
        file_id: str,
        storage_type: str,
        filename: str,
        gridfs_id: Union[str, ObjectId],
        nb_speakers: int
    ) -> InsertOneResult:
        """
        Add a new entry to the collection.
        Args:
            file_id: File identifier.
            storage_type: Storage type.
            filename: File name.
            gridfs_id: GridFS identifier.
            nb_speakers: Number of speakers.
        Returns:
            Insert result.
        Raises:
            RuntimeError: In case of insertion error.
        """
        data = {
            "file_id": file_id,
            "storage_type": storage_type,
            "filename": filename,
            "gridfs_id": gridfs_id,
            "nb_speakers": nb_speakers
        }
        try:
            return self._collection.insert_one(data)
        except Exception as e:
            raise RuntimeError(f"Error while inserting the document: {str(e)}")

    def _get_field(
        self,
        filename: str,
        field: str,
        error_message: str = "No document found for file '{filename}'."
    ) -> Any:
        """
        Retrieve a specific field for a given file.

        Args:
            filename: File name.
            field: Field name to retrieve.
            error_message: Custom error message.

        Returns:
            Value of the requested field.

        Raises:
            ValueError: If the file is not found.
            RuntimeError: In case of MongoDB error.
        """
        try:
            document = self._collection.find_one(
                {"filename": filename},
                {field: 1, "_id": 0}
            )
            if not document:
                raise ValueError(error_message.format(filename=filename))
            return document[field]
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve {filename}: {str(e)}")

    def get_infos_for_diarization(self, filename: str) -> Tuple[str, int]:
        """
        Retrieve the file identifier and number of speakers for a given file.
        """
        file_id = self._get_field(
            filename,
            "file_id",
            "No document found for file '{filename}'."
        )
        nb_speakers = self._get_field(
            filename,
            "nb_speakers",
            "No document found for file '{filename}'."
        )
        return file_id, nb_speakers

    def get_diarization_result(self, filename: str) -> List[Dict[str, Any]]:
        """
        Retrieve the diarization result for a given file.
        """
        return self._get_field(
            filename,
            "diarization_result",
            "No document found for file '{filename}'."
        )

    def get_sample_level_confidences(self, filename: str) -> Dict[str, Union[List[float], float]]:
        """
        Retrieve the sample-level confidences for a given file.
        """
        return self._get_field(
            filename,
            "sample_level_confidences",
            "No document found for file '{filename}'."
        )

    def get_gridfs_id(self, filename: str) -> Union[ObjectId, str]:
        """
        Retrieve the GridFS identifier for a given file.
        """
        return self._get_field(
            filename,
            "gridfs_id",
            "No document found for file '{filename}'."
        )

    def get_filenames_by_mean_scores(
        self,
        human_score_min: float,
        human_score_max: float,
        system_score_min: float,
        system_score_max: float
    ) -> List[Dict[str, Union[str, float]]]:
        """
        Retrieve files whose scores (human and system) fall within the specified ranges.

        Args:
            human_score_min: Minimum human score (inclusive).
            human_score_max: Maximum human score (inclusive).
            system_score_min: Minimum system score (sample_level_system_score, inclusive).
            system_score_max: Maximum system score (sample_level_system_score, inclusive).

        Returns:
            List of dictionaries containing for each file:
            - filename (str): File name.
            - human_score (float): Human score.
            - system_score (float): System score.

        Raises:
            ValueError: If no document matches the criteria.
            RuntimeError: In case of MongoDB query error.
        """
        try:
            query = {
                "$and": [
                    {"human_score": {"$gte": human_score_min, "$lte": human_score_max}},
                    {"sample_level_system_score": {"$gte": system_score_min, "$lte": system_score_max}}
                ]
            }

            projection = {
                "filename": 1,
                "human_score": 1,
                "sample_level_system_score": 1,
                "_id": 0
            }

            cursor = self._collection.find(query, projection)

            # Convert cursor to list of dictionaries
            documents = list(cursor)

            if not documents:
                raise ValueError("No document matches query.")

            return [
                {
                    "filename": doc["filename"],
                    "human_score": doc["human_score"],
                    "system_score": doc["sample_level_system_score"]
                }
                for doc in documents
            ]

        except Exception as e:
            raise RuntimeError(f"Failed to retrieve documents: {str(e)}")

    def get_number_of_documents(self) -> int:
        """
        Retrieve the total number of documents in the collection.

        Returns:
            int: Number of documents in the collection.

        Raises:
            RuntimeError: In case of MongoDB query error.
        """
        try:
            return self._collection.count_documents({})
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve number of documents: {str(e)}")

    def get_all_filenames(self) -> List[str]:
        """
        Retrieve a list of all unique filenames in the collection.

        Returns:
            List[str]: List of filenames.

        Raises:
            RuntimeError: In case of MongoDB query error.
        """
        try:
            return self._collection.distinct("filename")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve filenames: {str(e)}")

    def delete(self, filename: str) -> None:
        """
        Delete a document from the collection based on the filename.

        Args:
            filename (str): Name of the file to delete.

        Raises:
            RuntimeError: If the file is not found or in case of deletion error.
        """
        try:
            result = self._collection.delete_one({"filename": filename})

            if result.deleted_count == 0:
                raise RuntimeError(f"No file found with filename: {filename}.")
        except Exception as e:
            raise RuntimeError(f"Failed to delete file: '{filename}'.")

class GridfsStorageInterface():
    """
    Interface for managing audio files in GridFS.
    Allows adding, retrieving, and deleting audio files.
    """

    def __init__(self, database: Database, collection_name: str) -> None:
        """
        Initialize the GridFS interface for a given collection.
        Args:
            database: MongoDB database instance.
            collection_name: Name of the GridFS collection.
        """
        self._fs = GridFS(database, collection=collection_name)

    def register_audio(
        self,
        data: Union[BinaryIO, bytes],
        filename: str,
        content_type: str = "audio/wav"
    ) -> ObjectId:
        """
        Register an audio file in GridFS.
        Args:
            data: Binary file object or bytes of the audio file.
            filename: Name of the file to register.
            content_type: MIME type of the file (default: "audio/wav").
        Returns:
            ObjectId: The GridFS identifier of the registered file.
        Raises:
            ValueError: If the file cannot be read or is empty.
            RuntimeError: In case of registration error.
        """
        try:
            file_id = self._fs.put(data, filename=filename, contentType=content_type)
            return file_id
        except Exception as e:
            raise RuntimeError(f"Impossible to register the file: {str(e)}")

    def return_audio_byte(self, gridfs_id: Union[str, ObjectId]) -> Tuple[bytes, str]:
        """
        Retrieve an audio file as bytes from GridFS.
        Args:
            gridfs_id: GridFS ID of the file to retrieve.

        Returns:
            Tuple[bytes, str]: Binary content and MIME type of the audio file.

        Raises:
            ValueError: If the ID is invalid or the file is not found.
        """
        try:
            if isinstance(gridfs_id, str):
                gridfs_id = ObjectId(gridfs_id)
            audio_file = self._fs.get(gridfs_id)
            return audio_file.read(), audio_file.content_type
        except Exception as e:
            raise ValueError(f"Impossible to retrieve the file: {str(e)}")

    def delete(self, filename: str) -> None:
        """
        Delete a file from GridFS.
        Args:
            filename: Name of the file to delete.
        Raises:
            ValueError: If the file does not exist.
            RuntimeError: In case of deletion error.
        """
        try:
            file_infos = self._fs.find_one({"filename": filename})
            if not file_infos:
                raise ValueError(f"No document found for the file '{filename}'.")
            self._fs.delete(file_infos._id)
        except Exception as e:
            raise RuntimeError(f"Impossible to delete the file: {str(e)}")

    def check_filename_not_registered(self, filename: str) -> None:
        """
        Check if a file is already registered in GridFS.
        Args:
            filename: Name of the file to check.
        Raises:
            ValueError: If the file already exists.
            RuntimeError: In case of retrieval error.
        """
        try:
            result = self._fs.find_one({"filename": filename})
            if result:
                raise ValueError(f"File already registered in audio storage.")
        except Exception as e:
            raise RuntimeError(f"Error while retrieving the file: {str(e)}")


