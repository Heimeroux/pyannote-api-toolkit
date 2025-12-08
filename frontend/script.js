let numberOfDocuments = 0;
let registeredFilenames = [];
let listIds = ["filenameLists", "filenameSVG", "filenameDiarisation", "filenameListening", "filenameDeletion", "filenameSample", "filenameTurn"];

/**
 * Called during initialization to refresh all data and UI elements.
 */
refreshData();

/**
 * Updates the displayed value when a slider is moved.
 */
document.getElementById("humanBorneInfSlider").addEventListener("input", function() {
    document.getElementById("humanBorneInfDisplay").textContent = this.value;
});

document.getElementById("humanBorneSupSlider").addEventListener("input", function() {
    document.getElementById("humanBorneSupDisplay").textContent = this.value;
});

document.getElementById("sampleLevelBorneInfSlider").addEventListener("input", function() {
    document.getElementById("sampleLevelBorneInfDisplay").textContent = this.value;
});

document.getElementById("sampleLevelBorneSupSlider").addEventListener("input", function() {
    document.getElementById("sampleLevelBorneSupDisplay").textContent = this.value;
});

document.getElementById("frameBorneInfSlider").addEventListener("input", function() {
    document.getElementById("frameBorneInfDisplay").textContent = this.value;
});

document.getElementById("frameBorneSupSlider").addEventListener("input", function() {
    document.getElementById("frameBorneSupDisplay").textContent = this.value;
});

document.getElementById("turnBorneInfSlider").addEventListener("input", function() {
    document.getElementById("turnBorneInfDisplay").textContent = this.value;
});

document.getElementById("turnBorneSupSlider").addEventListener("input", function() {
    document.getElementById("turnBorneSupDisplay").textContent = this.value;
});

/**
 * Updates the filename text section (for uploading) when the user selects an audio recording.
 */
document.getElementById('audio').addEventListener('change', function() {
    const file = this.files[0];
    if (file) {
        const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
        document.getElementById('filenameUpload').value = nameWithoutExt;
    }
});


/**
 * Fetches the number of documents from the database.
 */
async function getNumberOfDocuments() {
    try {
        const response = await fetch('/get_number_of_documents', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error while requesting the number of documents");

        console.log('Success:', result);
        numberOfDocuments = result["nb_of_docs"];
    } catch (error) {
        console.error('Error:', error);
    }
}

/**
 * Fetches all filenames from the database.
 */
async function getAllFilenames() {
    try {
        const response = await fetch('/get_all_filenames', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error while requesting filenames");

        console.log('Success:', result);
        registeredFilenames = result["filenames"];
    } catch (error) {
        console.error('Error:', error);
    }
}

/**
 * Updates the list of filenames with new filenames.
 */
async function updateFilenamesFields(listId) {
    const newStorageTypes = registeredFilenames.map(item => ({
        value: item,
        label: item
    }));
    
    const selectElement = document.getElementById(listId);
    const existingOptions = Array.from(selectElement.options).slice(1);
    const existingValues = existingOptions.map(option => option.value);

    const newOptionsToAdd = newStorageTypes.filter(
        type => !existingValues.includes(type.value)
    );

    newOptionsToAdd.forEach(type => {
        const option = document.createElement("option");
        option.value = type.value;
        option.textContent = type.label;
        selectElement.appendChild(option);
    });

}

/**
 * Refreshes the displayed values for each slider when the page is refreshed.
 */
async function refreshSlidersDisplay() {
    document.getElementById("humanBorneInfDisplay").textContent = document.getElementById("humanBorneInfSlider").value;

    document.getElementById("humanBorneSupDisplay").textContent = document.getElementById("humanBorneSupSlider").value;

    document.getElementById("sampleLevelBorneInfDisplay").textContent = document.getElementById("sampleLevelBorneInfSlider").value;

    document.getElementById("sampleLevelBorneSupDisplay").textContent = document.getElementById("sampleLevelBorneSupSlider").value;

    document.getElementById("frameBorneInfDisplay").textContent = document.getElementById("frameBorneInfSlider").value;

    document.getElementById("frameBorneSupDisplay").textContent = document.getElementById("frameBorneSupSlider").value;

    document.getElementById("turnBorneInfDisplay").textContent = document.getElementById("turnBorneInfSlider").value;

    document.getElementById("turnBorneSupDisplay").textContent = document.getElementById("turnBorneSupSlider").value;
}

/**
 * Refreshes all data and UI elements.
 */
async function refreshData() {
    try {
        await Promise.all([
            getNumberOfDocuments(),
            getAllFilenames(),
            refreshSlidersDisplay()
        ]);
        
        for (const listId of listIds) {
            updateFilenamesFields(listId);
        }
    } catch (error) {
        console.error("Error during initialization:", error);
    }
}

/**
 * Resets file input fields after an upload attempt.
 */
function resetFileInputFields() {
    const audioInput = document.getElementById('audio');
    const filenameInput = document.getElementById('filenameUpload');

    audioInput.value = "";
    filenameInput.value = "";
}

/**
 * Fills a table with data.
 */
function fillTable(tableId, data, columns) {
    const tableBody = document.querySelector(`#${tableId} tbody`);
    tableBody.innerHTML = "";
    console.log('data:', data);

    data.forEach(item => {
        const row = document.createElement("tr");

        columns.forEach(column => {
            const cell = document.createElement("td");
            cell.textContent = item[column];
            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });
}

/**
 * Plays the audio.
 */
async function playAudio() {
    try {
        const audioPlayer = document.getElementById("audioPlayer");
        audioPlayer.play();
        console.log('Audio playback success');
    } catch (error) {
        console.error('Error:', error);
    }
}

/**
 * Deletes an option from a dropdown list by its value.
 */
function deleteOptionByValue(listId, valeur) {
    const dropdownList = document.getElementById(listId);

    for (let i = 0; i < dropdownList.options.length; i++) {
        if (dropdownList.options[i].value === valeur) {
            dropdownList.remove(i);
            console.log(`Option with value "${value}" deleted.`);
            return;
        }
    }

    console.log(`Option with value "${value}" not found.`);
}

/**
 * Cleans up data by removing a filename from all dropdown lists.
 */
async function cleanData(valeur) {
    try {
        for (const listId of listIds) {
            deleteOptionByValue(listId, valeur);
        }
    } catch (error) {
        console.error("Error during refresh after deletion:", error);
    }
}


/**
 * Handles the submission of the audio upload form.
 */
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const audioInput = document.getElementById('audio');
    const audioFile = audioInput.files[0];
    const filenameInput = document.getElementById('filenameUpload');
    const storageSelect = document.getElementById('storageType');
    const integerInput = document.getElementById('nbSpeakers');

    const nbSpeakers = integerInput.value;
    if (!nbSpeakers) {
        console.log("Please select a number of speakers.");
        return;
    }

    if (!audioFile) {
        console.log("Please select a file.");
        return;
    }

    // Wav verification
    const contentType = audioFile.type;
    const mimeOk = contentType === "audio/wav" || contentType === "audio/x-wav";
    const extensionOk = audioFile.name.toLowerCase().endsWith(".wav");

    if (!mimeOk || !extensionOk) {
        console.log("The file must be a WAV file (.wav).");
        resetFileInputFields();
        return;
    }
    
    const filename = filenameInput.value.trim();
    if (!filename) {
        console.log("Please enter a filename.");
        return;
    }
                

    const storageType = storageSelect.value;
    if (!storageType) {
        console.log("Please select a storage type.");
        return;
    }
    
    
    const formData = new FormData();
    const fileId = "file-" + (numberOfDocuments + 1);
    formData.append('file', audioFile);
    formData.append('filename', filename);
    formData.append('storage_type', storageType);
    formData.append('file_id', fileId);
    formData.append('content_type', contentType);
    formData.append('nb_speakers', nbSpeakers);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during upload");
        await refreshData();
        console.log('Success:', result);
    } catch (error) {
        console.error('Error:', error);
    }
    resetFileInputFields();
});

/**
 * Handles the submission of the diarization request form.
 */
document.getElementById('diarisationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const filenameInput = document.getElementById('filenameDiarisation');
    const filename = filenameInput.value;
    if (!filename) {
        console.log("Please enter a filename.");
        return;
    }
    
    try {
        const response = await fetch('/diarise', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename })
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during diarization request");
        console.log('Success:', result);
    } catch (error) {
        console.error('Error:', error);
    }

});

/**
 * Handles the submission of the SVG diagram loading form.
 */
document.getElementById("svgForm").addEventListener("submit", function(event) {
    event.preventDefault();

    const filename = document.getElementById("filenameSVG").value;
    if (!filename) {
        console.log("Veuillez entrer un nom de fichier.");
        return;
    }

    fetch(`/plot?filename=${encodeURIComponent(filename)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            return response.text();
        })
        .then(svgContent => {
            document.getElementById("plot-container").innerHTML = svgContent;
        })
        .catch(error => {
            console.error("Error retrieving SVG:", error);
            document.getElementById("plot-container").innerHTML =
                `<p style="color: red;">The file ${filename} has not been diarized yet! Please proceed with diarization first.</p>`;
        });
});

/**
 * Handles the change event for the audio file listening dropdown.
 */
document.getElementById('filenameListening').addEventListener('change', async function() {
    try {
        const filenameInput = document.getElementById('filenameListening');
    
        const filename = filenameInput.value;
        if (!filename) {
            console.log("Please enter a filename.");
            return;
        }
        
        const response = await fetch(`/get_audio_bytes?filename=${encodeURIComponent(filename)}`, {
            method: 'GET',
        });

        const audioBlob = await response.blob();
        if (!response.ok) throw new Error("Error retrieving audio bytes");

        const audioUrl = URL.createObjectURL(audioBlob);
        const audioPlayer = document.getElementById("audioPlayer");
        audioPlayer.src = audioUrl;
        
        console.log('Audio retrieval success');
    } catch (error) {
        console.error('Error:', error);
    }
});


/**
 * Handles the submission of the user score form.
 */
document.getElementById('integerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const integerInput = document.getElementById('integerInput');
    const filenameInput = document.getElementById('filenameLists');
    
    const filename = filenameInput.value;
    if (!filename) {
        console.log("Please enter a filename.");
        return;
    }
                

    const integer = integerInput.value;
    if (!integer) {
        console.log("Please select a score.");
        return;
    }
    
    try {
        const response = await fetch('/update_human_score', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: filename, human_score: integer })
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during score update request");

        console.log('Success:', result);
    } catch (error) {
        console.error('Error:', error);
    }
});

/**
 * Handles the submission of the deletion request form.
 */
document.getElementById('deletionForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const filenameInput = document.getElementById('filenameDeletion');
    const filename = filenameInput.value;
    if (!filename) {
        console.log("Please enter a filename.");
        return;
    }
    
    try {
        const response = await fetch('/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename })
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during deletion request");

        await cleanData(filename);
        console.log('Success:', result);
    } catch (error) {
        console.error('Error:', error);
    }

});

/**
 * Handles the submission of the form to retrieve files based on average confidence scores.
 */
document.getElementById('selectMeanForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const minValueHuman = parseInt(document.getElementById("humanBorneInfSlider").value);
    const maxValueHuman = parseInt(document.getElementById("humanBorneSupSlider").value);
    
    if (minValueHuman >= maxValueHuman) {
        console.log("The lower human score bound must be less than the upper bound.");
        return;
    }

    const minValueSample = parseInt(document.getElementById("sampleLevelBorneInfSlider").value);
    const maxValueSample = parseInt(document.getElementById("sampleLevelBorneSupSlider").value);
    
    if (minValueSample >= maxValueSample) {
        console.log("The lower sample score bound must be less than the upper bound.");
        return;
    }

    const baseUrl = "/get_filenames_by_mean_scores";
    const url = new URL(baseUrl, window.location.origin);

    url.searchParams.append("human_score_min", minValueHuman);
    url.searchParams.append("human_score_max", maxValueHuman);
    url.searchParams.append("sample_score_min", minValueSample);
    url.searchParams.append("sample_score_max", maxValueSample);
    
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during filenames request");
        console.log('Success:', result);

        const columns = ["filename", "human_score", "system_score"];
        fillTable("tabMeanThreshold", result["result"], columns);
        
    } catch (error) {
        console.error('Error:', error);
    }
});

/**
 * Handles the submission of the form to analyze sample-level confidence.
 */
document.getElementById('selectSampleLevelForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const minValueFrame = parseInt(document.getElementById("frameBorneInfSlider").value);
    const maxValueFrame = parseInt(document.getElementById("frameBorneSupSlider").value);
    
    if (minValueFrame >= maxValueFrame) {
        console.log("The lower frame score bound must be less than the upper bound.");
        return;
    }

    const filenameInput = document.getElementById('filenameSample');
    
    const filename = filenameInput.value.trim();
    if (!filename) {
        console.log("Please choose a file.");
        return;
    }

    const baseUrl = "/get_sample_level_confidences_by_filename";
    const url = new URL(baseUrl, window.location.origin);

    url.searchParams.append("min_score", minValueFrame);
    url.searchParams.append("max_score", maxValueFrame);
    url.searchParams.append("filename", filename);
    
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during filenames request");
        console.log('Success:', result);

        const columns = ["confidence", "start", "end"];
        fillTable("tabSampleThreshold", result["result"], columns);
        
    } catch (error) {
        console.error('Error:', error);
    }
});

/**
 * Handles the submission of the form to analyze turn-level confidence.
 */
document.getElementById('selectTurnLevelForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const minValueTurn = parseInt(document.getElementById("turnBorneInfSlider").value);
    const maxValueTurn = parseInt(document.getElementById("turnBorneSupSlider").value);
    
    if (minValueTurn >= maxValueTurn) {
        console.log("The lower turn score bound must be less than the upper bound.");
        return;
    }

    const filenameInput = document.getElementById('filenameTurn');
    
    const filename = filenameInput.value.trim();
    if (!filename) {
        console.log("Please choose a file.");
        return;
    }

    const baseUrl = "/get_turn_level_confidences_by_filename";
    const url = new URL(baseUrl, window.location.origin);

    url.searchParams.append("min_score", minValueTurn);
    url.searchParams.append("max_score", maxValueTurn);
    url.searchParams.append("filename", filename);
    
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.details || "Error during filenames request");

        console.log('Success:', result);

        const columns = ["start", "end", "speaker", "speaker_confidence"];
        fillTable("tabTurnThreshold", result["result"], columns);
        
    } catch (error) {
        console.error('Error:', error);
    }
});