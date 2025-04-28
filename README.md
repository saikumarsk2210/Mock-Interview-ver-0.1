# AI Mock Interview Practice Application

## Description

This project is a web-based application designed to help users practice for job interviews. Users can upload their resume, and the application uses AI (Google Gemini) to generate relevant technical and behavioral interview questions. The questions are delivered via Text-to-Speech (TTS), and the user can respond using their microphone (Speech-to-Text via Web Speech API). The application provides simple feedback notes after each answer and generates a final report summarizing the session.

This tool aims to help users:
*   Gain confidence by practicing answers aloud.
*   Receive tailored questions based on their own resume.
*   Get accustomed to the interview format.
*   Receive basic feedback on their responses.

## Features

*   **Resume Upload:** Accepts PDF and DOCX resume files.
*   **AI Question Generation:** Uses Google Gemini API to analyze resume text and generate relevant interview questions (mix of technical & behavioral). Currently set to generate 10 questions.
*   **Text-to-Speech (TTS):** Uses Hugging Face Transformers (`microsoft/speecht5_tts` model) to read out greetings, questions, and acknowledgements in an AI voice ("Rose").
*   **Speech-to-Text (STT):** Uses the browser's built-in Web Speech API to capture the user's spoken answers.
*   **AI Evaluation (Simple):** Uses Google Gemini API to provide a brief acknowledgement and a concise evaluation note for each answer.
*   **Interactive Flow:** Simulates a basic interview conversation flow (Greeting -> Q -> A -> Ack -> Next Q...).
*   **Final Report:** Generates an HTML report summarizing the questions, user answers, and evaluation notes.
*   **(Optional) PDF Report Download:** Includes functionality to download the report as a PDF (requires WeasyPrint system dependencies).

## Tech Stack

*   **Backend:** Python, Flask
*   **AI (LLM):** Google Gemini API (`gemini-1.5-flash-latest` via `google-generativeai` library)
*   **AI (TTS):** Hugging Face `transformers`, `torch`, `datasets`, `soundfile` (`microsoft/speecht5_tts` model with CMU ARCTIC xvectors)
*   **AI (STT):** Browser Web Speech API (JavaScript)
*   **Resume Parsing:** `PyPDF2`, `python-docx`
*   **Environment Variables:** `python-dotenv`
*   **PDF Generation (Optional):** `WeasyPrint`
*   **Frontend:** HTML, CSS, JavaScript

## Setup and Installation

Follow these steps to run the application locally:

1.  **Prerequisites:**
    *   Python 3.8+ installed.
    *   `pip` (Python package installer).
    *   Git (for cloning).
    *   **(Optional for PDF):** WeasyPrint system dependencies installed (Pango, Cairo, etc.). Follow instructions for your OS: [WeasyPrint Installation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)

2.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-folder-name> # e.g., cd interview-mock-1
    ```

3.  **Create and Activate Virtual Environment:**
    ```bash
    # Create venv (use python3 if python maps to python 2)
    python -m venv venv

    # Activate venv
    # Windows (PowerShell)
    .\venv\Scripts\Activate.ps1
    # Windows (Command Prompt)
    .\venv\Scripts\activate.bat
    # macOS / Linux
    source venv/bin/activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(This might take a while, especially downloading PyTorch and Transformers models).*

5.  **Set Up Environment Variables:**
    *   Create a file named `.env` in the root project directory.
    *   Add your API keys and a secret key to this file:
        ```dotenv
        GOOGLE_API_KEY='YOUR_GOOGLE_GEMINI_API_KEY_HERE'
        FLASK_SECRET_KEY='YOUR_GENERATED_FLASK_SECRET_KEY_HERE'
        ```
    *   Replace `YOUR_GOOGLE_GEMINI_API_KEY_HERE` with your actual key from Google AI Studio.
    *   Generate a Flask secret key by running `python -c "import secrets; print(secrets.token_hex(32))"` in your terminal and paste the result for `YOUR_GENERATED_FLASK_SECRET_KEY_HERE`.
    *   **Important:** Ensure `.env` is listed in your `.gitignore` file!

6.  **Run the Application:**
    ```bash
    python app.py
    ```

7.  **Access the App:** Open your web browser and navigate to `http://127.0.0.1:5000` (or the address provided in the terminal).

## Usage

1.  Navigate to the home page (`http://127.0.0.1:5000`).
2.  Click "Choose File" and select your resume (PDF or DOCX).
3.  Click "Upload & Generate Questions". You will be redirected to the interview page.
4.  Click the "Start Interview" button.
5.  Allow microphone access if prompted by your browser.
6.  Listen to the interviewer's greeting/question.
7.  Click "Record Answer", speak clearly, and click "Stop Recording" (or wait for the silence timer).
8.  Listen to the interviewer's acknowledgement.
9.  The next question will be asked automatically. Repeat steps 7-8.
10. After the last question, listen to the closing statement.
11. You will be redirected to the report page.
12. (Optional) Click the "Download Report as PDF" button if available.

## Configuration (Optional)

*   **TTS Voice:** You can change the AI interviewer's voice by modifying the `speaker_index` variable in `tts_interface.py`. Experiment with different indices from the CMU ARCTIC dataset.
*   **STT Silence Timeout:** Adjust the `SILENCE_TIMEOUT` constant (in milliseconds) in `static/js/interview.js` to change how long the system waits for silence before stopping recording.
*   **PDF Generation:** If PDF download fails, ensure WeasyPrint system dependencies are correctly installed for your operating system.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details (if you add one).

## Future Work / Ideas

*   Implement more sophisticated answer evaluation using LLMs (scoring relevance, STAR method).
*   Add support for different interview types (purely behavioral, specific technical roles).
*   Integrate more robust STT services (e.g., Whisper, Google Cloud STT) for better accuracy and potential fluency analysis (ums, ahs).
*   Allow users to select different TTS voices.
*   Improve UI/UX, add visual feedback during processing.
*   Store interview history for users (requires database integration).
