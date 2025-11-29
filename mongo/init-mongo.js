db = db.getSiblingDB("pyannote_api_infos");

// The collection stores everything related to the audio file
// Need a validation schema to be sure that added data corresponds to the structure of the collection
db.createCollection("file_infos", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            title: "Audio File Object Validation",
            required: ["stockage_type", "filename", "gridfs_id"],
            properties: {
                human_score: {
                    bsonType: "int",
                    minimum: 0,
                    maximum: 100,
                    description: "Score given by the user after the diarization process. The higher is the score, the more the result is appreciated by the user."
                },
                system_score: {
                    bsonType: "double",
                    minimum: 0.0,
                    maximum: 100.0,
                    description: "Mean confidence score given by the system over the diarization process. The higher is the score, the more confident is the system."
                },
                diarization_result: {
                    bsonType: "array",
                    items: {
                        bsonType: "object",
                        required: ["start", "end", "speaker"],
                        properties: {
                            start: {
                                bsonType: "double",
                                minimum: 0.0
                            },
                            end: {
                                bsonType: "double",
                                minimum: 0.0
                            },
                            speaker: {bsonType: "string"}
                        }
                    },
                    description: "Output of the system after processing diarization on the file."
                },
                file_path: {
                    bsonType: "string",
                    description: "Path of the file location in the storage system."
                },
                stockage_type: {
                    bsonType: "string",
                    enum: ["PyAnnote", "S3"],
                    description: "File must be web stocked either using PyAnnote or Amazon S3."
                },
                filename: {
                    bsonType: "string",
                    description: "Local name of the file."
                },
                gridfs_id: {
                    bsonType: "objectId",
                    description: "ID created by MongoDB when the audio file have been registered."
                }
            }
        }
    }
});

db.file_infos.createIndex({"filename": 1}, {unique: true});

// Collection designed to store audio files as multiple audio chunks
db.createCollection('audio_storage.files');
db.createCollection('audio_storage.chunks');

//db.createCollection("pyannote_file");
//db.createCollection("human_voiceprint");