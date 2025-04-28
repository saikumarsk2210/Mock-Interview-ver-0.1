// static/js/interview.js (Reverted to simpler version)

console.log("interview.js script executing...");

// --- DOM Elements ---
let startButton = null; let recordButton = null; let stopButton = null;
let messagesDiv = null; let statusDiv = null; let audioPlayer = null;

// --- State Variables ---
let currentInterviewState = null; let recognition = null; let isRecording = false;
let currentUtteranceTranscript = ''; let silenceTimer = null;
const SILENCE_TIMEOUT = 3500; let currentMessageElement = null;

// --- Web Speech API Setup ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    try {
        console.log("Initializing SpeechRecognition...");
        recognition = new SpeechRecognition();
        recognition.continuous = true; recognition.interimResults = true; recognition.lang = 'en-US';

        recognition.onstart = () => {
            console.log('SR started'); isRecording = true; currentUtteranceTranscript = '';
            if(recordButton) { recordButton.textContent = 'Recording...'; recordButton.disabled = true; }
            if(stopButton) stopButton.disabled = false; if(statusDiv) statusDiv.textContent = 'Listening...';
            currentMessageElement = createNewUserMessageElement("(Speaking...)"); resetSilenceTimer();
        };
        recognition.onresult = (event) => {
            resetSilenceTimer(); let interim = ''; let finalSegment = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const part = event.results[i][0].transcript;
                if (event.results[i].isFinal) { finalSegment += part; } else { interim += part; }
            }
            if (currentMessageElement) { updateCurrentMessageVisual(currentUtteranceTranscript + finalSegment + interim); }
            console.log("Interim: ", interim);
            if (finalSegment) { currentUtteranceTranscript += finalSegment.trim() + ' '; }
        };
        recognition.onerror = (event) => {
            console.error('SR error:', event.error, event.message); let msg = `Recog Error: ${event.error}.`;
            if (event.error === 'no-speech') { msg = 'No speech detected.'; } else if (event.error === 'audio-capture') { msg = 'Mic error.'; } else if (event.error === 'not-allowed') { msg = 'Mic access denied.'; }
            if(statusDiv) statusDiv.textContent = msg + " Try again."; clearTimeout(silenceTimer); if (isRecording) { stopRecognitionInternal(); }
            if (currentMessageElement && currentMessageElement.textContent === "(Speaking...)") { currentMessageElement.remove(); currentMessageElement = null; }
        };
        recognition.onend = () => {
            console.log('SR ended.'); clearTimeout(silenceTimer); if (!isRecording && currentUtteranceTranscript === '') { console.log("onend skipped"); return; }
            isRecording = false; if(recordButton) recordButton.textContent = 'Record Answer'; if(stopButton) stopButton.disabled = true;
            const completeAnswer = currentUtteranceTranscript.trim(); console.log("Final Answer: ", completeAnswer);
            if (currentMessageElement) { finalizeCurrentMessageVisual(completeAnswer || "(No answer)"); currentMessageElement = null; }
            if (completeAnswer) { if(statusDiv) statusDiv.textContent = 'Processing...'; sendAnswerToServer(completeAnswer); }
            else { if(statusDiv) statusDiv.textContent = 'No clear answer. Try again?'; enableRecordingIfNeeded(); }
            currentUtteranceTranscript = '';
        };
    } catch (e) { console.error("SR Init failed:", e); if(statusDiv) statusDiv.textContent = 'SR setup failed.'; disableAllControls(); recognition = null; }
} else { console.error('SR not supported.'); if(statusDiv) statusDiv.textContent = 'SR not supported.'; disableAllControls(); }

// --- Silence Timer ---
function resetSilenceTimer() { clearTimeout(silenceTimer); silenceTimer = setTimeout(() => { if (isRecording && recognition) { console.log("Silence detected."); recognition.stop(); } }, SILENCE_TIMEOUT); }

// --- Control & State Update ---
function disableAllControls() { if(startButton) startButton.disabled = true; if(recordButton) recordButton.disabled = true; if(stopButton) stopButton.disabled = true; }
function enableRecordingIfNeeded() {
    // Enable recording only if expecting greeting response OR question answer
    const shouldBeEnabled = (currentInterviewState === 'AWAITING_GREETING_RESPONSE' || currentInterviewState === 'LISTENING');
    if(recordButton) recordButton.disabled = !shouldBeEnabled;
    console.log(`Record button ${recordButton?.disabled ? 'disabled' : 'enabled'} (State: ${currentInterviewState})`);
}

// --- Main Flow ---
function startInterview() {
    console.log('startInterview called!'); if (!startButton || !statusDiv) return;
    disableAllControls(); statusDiv.textContent = 'Initializing...';
    fetch('/interview/start', { method: 'POST' })
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then(data => { if (data.error) throw new Error(data.error); handleServerResponse(data); })
        .catch(e => { console.error('Start error:', e); if(statusDiv) statusDiv.textContent = `Error starting: ${e.message}`; if(startButton) startButton.disabled = false; });
}
function startRecognition() { if (recognition && !isRecording) { try { recognition.start(); } catch (e) { console.error("Mic Error:", e); if(statusDiv) statusDiv.textContent = `Mic Error: ${e.message}`; stopRecognitionInternal(); } } else if (!recognition) { if(statusDiv) statusDiv.textContent = 'SR unavailable.'; } }
function stopRecordingManual() { clearTimeout(silenceTimer); if (recognition && isRecording) { console.log("Manual stop."); recognition.stop(); } }
function stopRecognitionInternal() { clearTimeout(silenceTimer); if (recognition && isRecording) { isRecording = false; recognition.abort(); console.log("SR aborted."); } else { isRecording = false; } if(recordButton) recordButton.textContent = 'Record Answer'; if(stopButton) stopButton.disabled = true; enableRecordingIfNeeded(); }

function sendAnswerToServer(answerText) {
    console.log(`Sending to server (State: ${currentInterviewState}): ${answerText.substring(0, 50)}...`);
    if(statusDiv) statusDiv.textContent = 'Processing...'; disableAllControls();
    fetch('/interview/next_step', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: answerText }) })
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(data => { console.log('Server response:', data); if (data.error) throw new Error(data.error); handleServerResponse(data); })
    .catch(error => { console.error('Send error:', error); if(statusDiv) statusDiv.textContent = `Error: ${error.message}. Try again?`; enableRecordingIfNeeded(); });
}

// --- Central Response Handler (SIMPLIFIED) ---
function handleServerResponse(data) {
    currentInterviewState = data.state; // Update state FIRST

    if (data.transcript) { appendMessage(data.transcript, 'interviewer'); }

    if (data.is_finished) {
        if(statusDiv) statusDiv.textContent = 'Interview finished.'; disableAllControls();
        if (data.audio_url) { playAudio(data.audio_url, () => { if(statusDiv) statusDiv.textContent = 'Redirecting...'; window.location.href = '/report'; }); }
        else { if(statusDiv) statusDiv.textContent = 'Redirecting...'; window.location.href = '/report'; }

    } else if (data.state === 'AWAITING_GREETING_RESPONSE' || data.state === 'LISTENING') {
        // Received greeting OR a question, expect user input next
        if(statusDiv) statusDiv.textContent = 'Interviewer speaking...'; disableAllControls(); // Keep disabled during audio
        if (data.audio_url) { playAudio(data.audio_url, () => { if(statusDiv) statusDiv.textContent = 'Ready for your response.'; enableRecordingIfNeeded(); }); } // Enable recording AFTER audio
        else { if(statusDiv) statusDiv.textContent = 'Ready for response (no audio).'; enableRecordingIfNeeded(); } // Enable immediately

    } else if (data.state === 'GREETING_ACKNOWLEDGED' || data.state === 'ACKNOWLEDGED_ANSWER') {
        // Received an acknowledgement, trigger next step automatically
        if(statusDiv) statusDiv.textContent = 'Acknowledged... Getting next step...'; disableAllControls();
        if (data.audio_url) { playAudio(data.audio_url, () => sendAnswerToServer("")); }
        else { sendAnswerToServer(""); }

    } else if (data.state === 'ASKING_QUESTION') {
         // This state might be momentarily passed through from backend but JS mainly reacts to LISTENING
         if(statusDiv) statusDiv.textContent = 'Interviewer asking...'; disableAllControls();
         if (data.audio_url) { playAudio(data.audio_url, () => { if(statusDiv) statusDiv.textContent = 'Ready for your answer.'; currentInterviewState = 'LISTENING'; enableRecordingIfNeeded(); }); } // Set LISTENING after audio
         else { if(statusDiv) statusDiv.textContent = 'Ready for answer (no audio).'; currentInterviewState = 'LISTENING'; enableRecordingIfNeeded(); }

    } else {
         console.warn("Unexpected state in simple handler:", data.state); if(statusDiv) statusDiv.textContent = `Error: Unexpected state ${data.state}.`; disableAllControls();
    }
}

// --- Utility Functions ---
function appendMessage(text, sender) { // Keep as is
    if (!messagesDiv) return null; const msg = document.createElement('div'); msg.className = `message ${sender}-message`; msg.textContent = text;
    if (sender === 'user') { const old = document.getElementById('current-user-message'); if(old) old.id = ""; msg.id = 'current-user-message'; }
    messagesDiv.appendChild(msg); messagesDiv.scrollTop = messagesDiv.scrollHeight; return msg;
}
function createNewUserMessageElement(placeholderText = "") { // Keep as is
    if (!messagesDiv) return null; const oldCurrent = document.getElementById('current-user-message'); if (oldCurrent) { oldCurrent.id = ""; }
    const msg = appendMessage(placeholderText, 'user'); if (msg) { msg.style.opacity = 0.7; msg.style.fontStyle = 'italic'; } return msg;
}
function updateCurrentMessageVisual(text) { // Keep as is
    if(currentMessageElement) { currentMessageElement.textContent = text; currentMessageElement.style.opacity = 0.7; currentMessageElement.style.fontStyle = 'italic'; messagesDiv.scrollTop = messagesDiv.scrollHeight; }
    else { console.warn("updateCurrentMessageVisual: currentMessageElement is null."); }
}
function finalizeCurrentMessageVisual(text) { // Keep as is
     if(currentMessageElement) { currentMessageElement.textContent = text; currentMessageElement.style.opacity = 1; currentMessageElement.style.fontStyle = 'normal'; currentMessageElement.id = ""; }
     else { console.warn("finalizeCurrentMessageVisual: currentMessageElement is null."); const finalMsg = appendMessage(text, 'user'); if(finalMsg) finalMsg.id = ""; }
}
function playAudio(url, callback) { // Keep as is
    if (!audioPlayer) { console.error("Audio player missing!"); if(callback) callback(); return; } if (!url) { console.warn("playAudio no URL."); if(callback) callback(); return; }
    console.log(`Playing audio: ${url}`); audioPlayer.src = url;
    const onEnded = () => { console.log(`Audio ended: ${url}`); cleanupListeners(); if (callback) callback(); };
    const onError = (e) => { console.error(`Audio error ${url}:`, e); if(statusDiv) statusDiv.textContent = 'Audio error.'; cleanupListeners(); if (callback) callback(); };
    const onCanPlay = () => { console.log(`Audio can play: ${url}`); audioPlayer.play().then(() => console.log("Playback started.")).catch(onError); };
    const cleanupListeners = () => { audioPlayer.removeEventListener('ended', onEnded); audioPlayer.removeEventListener('error', onError); audioPlayer.removeEventListener('canplay', onCanPlay); };
    cleanupListeners(); audioPlayer.addEventListener('ended', onEnded); audioPlayer.addEventListener('error', onError); audioPlayer.addEventListener('canplay', onCanPlay, { once: true });
    audioPlayer.load();
}

// --- Event Listeners & Initial State ---
document.addEventListener('DOMContentLoaded', (event) => { // Keep as is
    console.log("DOM loaded.");
    startButton = document.getElementById('startButton'); recordButton = document.getElementById('recordButton'); stopButton = document.getElementById('stopButton');
    messagesDiv = document.getElementById('messages'); statusDiv = document.getElementById('status'); audioPlayer = document.getElementById('audioPlayer');
    if (!startButton || !recordButton || !stopButton || !messagesDiv || !statusDiv || !audioPlayer) { console.error("UI elements missing!"); if(statusDiv) statusDiv.textContent = "UI Error."; disableAllControls(); return; }
    else { console.log("UI elements assigned."); }
    startButton.addEventListener('click', startInterview); recordButton.addEventListener('click', startRecognition); stopButton.addEventListener('click', stopRecordingManual);
    disableAllControls(); startButton.disabled = false; statusDiv.textContent = 'Ready. Click Start.';
});
console.log("interview.js initial execution finished.");