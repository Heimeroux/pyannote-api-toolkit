db = db.getSiblingDB("pyannote_api_infos");

// The collection stores everything related to the audio file
// Need a validation schema to be sure that added data corresponds to the structure of the collection
db.createCollection("file_infos", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            title: "Audio File Object Validation",
            required: ["storage_type", "filename", "gridfs_id", "nb_speakers"],
            properties: {
                human_score: {
                    bsonType: "int",
                    minimum: 0,
                    maximum: 100,
                    description: "Score given by the user after the diarization process. The higher is the score, the more the result is appreciated by the user."
                },
                sample_level_system_score: {
                    bsonType: "double",
                    minimum: 0.0,
                    maximum: 100.0,
                    description: "Mean confidence score of regular intervals throughout the audio. The higher is the score, the more confident is the system."
                },
                diarization_result: {
                    bsonType: "array",
                    items: {
                        bsonType: "object",
                        required: ["start", "end", "speaker", "confidence"],
                        properties: {
                            start: {
                                bsonType: "double",
                                minimum: 0.0
                            },
                            end: {
                                bsonType: "double",
                                minimum: 0.0
                            },
                            speaker: {bsonType: "string"},
                            confidence: {bsonType: "object"}
                        }
                    },
                    description: "Output of the system after processing diarization on the file."
                },
                file_id: {
                    bsonType: "string",
                    description: "Id of the file to locate it in the storage system."
                },
                storage_type: {
                    bsonType: "string",
                    enum: ["PyAnnote"],
                    description: "File must be web stored using PyAnnote only. In the future I aim to allow other services such as S3."
                },
                filename: {
                    bsonType: "string",
                    description: "Local name of the file."
                },
                gridfs_id: {
                    bsonType: "objectId",
                    description: "ID created by MongoDB when the audio file have been registered."
                },
                job_id: {
                    bsonType: "string",
                    description: "ID of the job created when submitted a diarization. Value of the field must be deleted 24 hours after the job succeeded."
                },
                nb_speakers: {
                    bsonType: "int",
                    description: "Number of speakers in the audio recording. Must be between 1 and 100.",
                    minimum: 1,
                    maximum: 100,
                },
                sample_level_confidences: {
                    bsonType: "object",
                    required: ["score", "resolution"],
                    properties: {
                        score: {
                            bsonType: "array",
                            items: {
                                bsonType: "int",
                                minimum: 0,
                                maximum: 100
                            },
                        },
                        resolution: {
                            bsonType: "double",
                            minimum: 0.0
                        }
                    },
                    description: "Output from the system for the sample-level confidence."
                }
            }
        }
    }
});

// Use filename as an unique index
db.file_infos.createIndex({"filename": 1}, {unique: true});

// Collection designed to store audio files as multiple audio chunks
db.createCollection('audio_storage.files');
db.createCollection('audio_storage.chunks');
db.audio_storage.files.createIndex({"filename": 1}, {unique: true});

