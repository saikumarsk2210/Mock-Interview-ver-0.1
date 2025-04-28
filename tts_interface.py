# tts_interface.py (Using Speaker Index 6000)
import os
import time
import torch
import soundfile as sf
from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from datasets import load_dataset
import traceback # Import traceback

# Configuration
AUDIO_OUTPUT_DIR = "generated_audio"
ENABLE_HF_TTS = True # Set to False to disable TTS generation for testing flow
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Ensure audio directory exists
if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR)

# --- Hugging Face TTS Model Loading ---
processor = None; model = None; vocoder = None; speaker_embeddings = None
embeddings_dataset = None # Define it here

if ENABLE_HF_TTS:
    try:
        print(f"TTS Interface: Loading HF TTS models on device: {DEVICE}...")
        # Load models only once
        if processor is None: processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
        if model is None: model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts").to(DEVICE)
        if vocoder is None: vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan").to(DEVICE)

        print("TTS Interface: Loading speaker embeddings...")
        # Load dataset only once
        if embeddings_dataset is None: embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")

        # *** USING SPEAKER INDEX 6000 (Often 'slt' - female) ***
        speaker_index = 6000 # Changed to 6000
        # *** END CHANGE ***

        # Validate index and load embedding
        if speaker_index >= len(embeddings_dataset):
            print(f"Warning: Speaker index {speaker_index} out of bounds ({len(embeddings_dataset)} available). Using index 0.")
            speaker_index = 0 # Fallback to 0 if index is too high
        speaker_embeddings = torch.tensor(embeddings_dataset[speaker_index]["xvector"]).unsqueeze(0).to(DEVICE)
        print(f"TTS Interface: Using speaker embedding index: {speaker_index}")

        print("TTS Interface: HF TTS models and embeddings loaded successfully.")

    except ImportError:
        print("TTS Interface: Required libraries (transformers, datasets, torch, soundfile) not found. Disabling TTS.");
        ENABLE_HF_TTS = False
    except Exception as e:
        print(f"TTS Interface: Error loading HF TTS model or embeddings: {e}. Disabling TTS.");
        traceback.print_exc() # Print full traceback for loading errors
        ENABLE_HF_TTS = False

def text_to_speech(text_to_speak, filename_prefix="interview_audio"):
    """Generates audio from text using Hugging Face SpeechT5 TTS and saves it."""
    if not ENABLE_HF_TTS or not all([processor, model, vocoder, speaker_embeddings is not None]):
        print("TTS Interface: TTS Disabled or models not loaded. Cannot generate audio.")
        return None

    output_filename = None # Initialize
    output_filepath = None # Initialize
    try:
        # Add slight modifications for potential pauses (experimental)
        processed_text = text_to_speak.replace("?", "? ...").replace(".", ". ... ")
        print(f"TTS Interface: Generating audio for prefix '{filename_prefix}': '{processed_text[:80]}...'")
        start_time = time.time()

        inputs = processor(text=processed_text, return_tensors="pt").to(DEVICE)

        with torch.no_grad(): # Disable gradient calculation for inference
            spectrogram = model.generate_speech(inputs["input_ids"], speaker_embeddings)
            speech = vocoder(spectrogram)

        # Ensure speech is on CPU for numpy conversion
        speech_cpu = speech.cpu().numpy()

        timestamp = int(time.time() * 1000) # Use milliseconds for more uniqueness
        output_filename = f"{filename_prefix}_{timestamp}.wav"
        output_filepath = os.path.join(AUDIO_OUTPUT_DIR, output_filename)

        # Save the audio file (use float32, sample rate 16000Hz for SpeechT5)
        sf.write(output_filepath, speech_cpu, samplerate=16000, format='WAV', subtype='FLOAT') # Specify format/subtype

        end_time = time.time()

        # Verify file creation and size
        if os.path.exists(output_filepath) and os.path.getsize(output_filepath) > 100: # Check for > 100 bytes as sanity check
             print(f"TTS Interface: SUCCESS - Audio saved to '{output_filepath}' ({os.path.getsize(output_filepath)} bytes) in {end_time - start_time:.2f}s.")
             return output_filename # Return only filename on success
        else:
             print(f"TTS Interface: FAILURE - Audio file NOT created or empty at '{output_filepath}'.")
             if os.path.exists(output_filepath): # Attempt cleanup if empty file was created
                  try: os.remove(output_filepath)
                  except OSError: pass
             return None # Return None if file wasn't created properly

    except Exception as e:
        print(f"TTS Interface: Error during TTS generation/saving for '{filename_prefix}': {e}")
        traceback.print_exc() # Print full traceback
        # Attempt cleanup if file exists but might be corrupted
        if output_filepath and os.path.exists(output_filepath):
            try: os.remove(output_filepath); print(f"TTS Interface: Removed potentially corrupted file: {output_filepath}")
            except OSError: pass
        return None

def get_audio_filepath(filename):
    """Gets the full path for a generated audio file."""
    if not filename or os.path.sep in filename or ".." in filename:
        print(f"TTS Interface: Invalid or unsafe filename requested: {filename}")
        return None
    return os.path.join(AUDIO_OUTPUT_DIR, filename)