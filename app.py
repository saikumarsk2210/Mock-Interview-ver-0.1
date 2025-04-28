# app.py (Generate Secret Key on First Run if Missing)

import os
import re
import random
import PyPDF2
from PyPDF2 import errors as PyPDF2Errors
import docx
from flask import Flask, request, render_template, redirect, url_for, flash, session, send_from_directory, jsonify, make_response
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import google.generativeai as genai
import json
import traceback
import secrets # Import the secrets module

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except OSError as e: print("*"*60+"\nWARNING: WeasyPrint Import Error...\n"+"*"*60); WEASYPRINT_AVAILABLE = False
except ImportError: print("*"*60+"\nWARNING: WeasyPrint Not Found...\n"+"*"*60); WEASYPRINT_AVAILABLE = False

# --- Local Module Imports ---
from interview_manager import InterviewManager # Use the simpler manager
import tts_interface

# --- Configuration & Setup ---
load_dotenv()
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'; app.config['TTS_AUDIO_FOLDER'] = tts_interface.AUDIO_OUTPUT_DIR

# --- SECRET KEY GENERATION LOGIC ---
# Try to get SECRET_KEY from environment variable first
SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
if not SECRET_KEY:
    # If not found, generate a new one for this run
    print("WARNING: FLASK_SECRET_KEY not set in environment. Generating temporary key for this session.")
    print("         User sessions will NOT persist across server restarts.")
    print("         For persistent sessions, set FLASK_SECRET_KEY in your .env file.")
    SECRET_KEY = secrets.token_hex(32) # Generate a 32-byte hex key
    # You could optionally write this generated key to a .env file here if it doesn't exist,
    # but simply using it for the current run is often sufficient for dev.
    # For example (optional write):
    # if not os.path.exists('.env'):
    #    with open('.env', 'a') as f:
    #        f.write(f"\nFLASK_SECRET_KEY='{SECRET_KEY}'\n")
    #        print("   -> Wrote generated key to new .env file.")
else:
    print("Using FLASK_SECRET_KEY from environment.")

# Set the Flask secret key config
app.config['SECRET_KEY'] = SECRET_KEY
# --- END SECRET KEY LOGIC ---


if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['TTS_AUDIO_FOLDER']): os.makedirs(app.config['TTS_AUDIO_FOLDER'])

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY"); gemini_model = None
if not GEMINI_API_KEY: print("!!! WARNING: GOOGLE_API_KEY not set. Gemini disabled. !!!")
else:
    try: genai.configure(api_key=GEMINI_API_KEY); gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest'); print("Gemini configured.")
    except Exception as e: print(f"Error configuring Gemini: {e}. Disabled."); GEMINI_API_KEY = None

# --- Helper Functions (Keep as is) ---
def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx'}
def extract_text_from_pdf(filepath):
    text = "";
    try:
        with open(filepath, 'rb') as file:
            try: reader = PyPDF2.PdfReader(file, strict=False)
            except PyPDF2Errors.PyPdfError as init_err: raise ValueError(f"PDF reader init error: {init_err}")
            num_pages = len(reader.pages); print(f"Reading {num_pages} pages from PDF...")
            for i, page in enumerate(reader.pages):
                try: page_text = page.extract_text(); text += (page_text + " ") if page_text else ""
                except Exception as page_exc: print(f"  - Error page {i+1}: {page_exc}")
        text = re.sub(r'\s+', ' ', text).strip(); print(f"Extracted text from PDF: {os.path.basename(filepath)}")
    except PyPDF2Errors.PdfReadError as pe: raise ValueError(f"Could not read PDF structure: {pe}")
    except FileNotFoundError: raise
    except Exception as e: print(f"Unexpected error reading PDF: {e}"); traceback.print_exc(); raise ValueError(f"PDF processing error: {e}")
    return text
def extract_text_from_docx(filepath):
    text = "";
    try: doc = docx.Document(filepath); full_text = [p.text for p in doc.paragraphs if p.text]; text = ' '.join(full_text)
    except Exception as e: raise ValueError(f"Could not read DOCX: {e}")
    text = re.sub(r'\s+', ' ', text).strip(); print(f"Extracted text from DOCX: {os.path.basename(filepath)}")
    return text
def parse_resume(filepath):
    print(f"Starting text extraction for: {filepath}")
    if not os.path.exists(filepath): raise FileNotFoundError(f"Resume file not found: {filepath}")
    try:
        if filepath.lower().endswith(".pdf"): text = extract_text_from_pdf(filepath)
        elif filepath.lower().endswith(".docx"): text = extract_text_from_docx(filepath)
        else: raise ValueError(f"Unsupported type: {filepath}")
        if not text: raise ValueError(f"No text extracted: {filepath}")
        print(f"Text extraction complete. Length: {len(text)} chars.")
        return text
    except Exception as e: print(f"Error during parse_resume: {e}"); raise

# --- Gemini Interaction Functions (Keep as is - using simpler evaluation) ---
def generate_questions_with_gemini(resume_text):
    print("Generating 10 questions (incl. behavioral)...")
    if not gemini_model: return ["Gemini unavailable.", "Default Q."]
    prompt = f"""Act as recruiter reviewing resume:\n---\n{resume_text}\n---\nGenerate exactly 10 insightful interview questions (mix technical & behavioral). Format ONLY numbered list:\n1. Q1?\n...\n10. Q10?"""
    try:
        safety_settings = [ {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"] ]
        response = gemini_model.generate_content(prompt, safety_settings=safety_settings)
        if not response.parts: raise ValueError(f"Gemini Q-gen blocked: {response.prompt_feedback.block_reason}.")
        raw_questions = response.text.strip().split('\n'); questions = [re.match(r'^\s*\d+[.)]?\s*(.*)', l).group(1).strip() if re.match(r'^\s*\d+[.)]?\s*(.*)', l) else l.strip() for l in raw_questions if l.strip()]
        if not questions: raise ValueError("Gemini Q-gen parsing failed.")
        print(f"Generated {len(questions)} questions."); return questions
    except Exception as e: print(f"Error Gemini Q-gen: {e}"); traceback.print_exc(); return [f"Error Q-gen: {e}", "Fallback Q."]

def evaluate_and_respond_gemini_simple(question_asked, user_answer):
    print(f"Evaluating answer simply for Q: '{question_asked[:50]}...'")
    if not gemini_model: return "Okay.", "Evaluation skipped."
    prompt = f"""As AI interviewer 'Rose'. Question: "{question_asked}" Answer: "{user_answer}" Provide: 1. Short conversational acknowledgement (1 sentence, friendly/neutral). 2. Concise evaluation note (max 10 words) for a report. Handle "don't know"/refusals neutrally. Format *exactly*: ACKNOWLEDGEMENT: [Ack] EVALUATION: [Eval Note]"""
    try:
        safety_settings = [ {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"] ]
        response = gemini_model.generate_content(prompt, safety_settings=safety_settings)
        if not response.parts: raise ValueError(f"Gemini eval blocked: {response.prompt_feedback.block_reason}.")
        response_text = response.text.strip(); print(f"Gemini Simple Eval Raw:\n{response_text}")
        ack_match = re.search(r"ACKNOWLEDGEMENT:\s*(.*?)(?:\nEVALUATION:|$)", response_text, re.I | re.S); eval_match = re.search(r"EVALUATION:\s*(.*)", response_text, re.I)
        ack_text = ack_match.group(1).strip() if ack_match else "Got it."; eval_note = eval_match.group(1).strip() if eval_match else "Eval parse error."
        if eval_match and ack_text.endswith(eval_match.group(0)): ack_text = ack_text[:-len(eval_match.group(0))].strip()
        print(f"Simple Eval -> Ack: '{ack_text}', Eval Note: '{eval_note}'"); return ack_text, eval_note
    except Exception as e: print(f"Error Gemini simple eval: {e}"); traceback.print_exc(); return "Alright.", f"Eval error: {e}"

def generate_greeting_with_gemini():
    print("Generating greeting...")
    if not gemini_model:
        return "Hello! Let's begin."
    
    prompt = "You are 'Rose', a friendly AI interviewer. Generate 1-2 cheery opening sentences."
    try:
        response = gemini_model.generate_content(prompt)
        greeting = response.text.strip()
        greeting = re.sub(r'^"|"$|^(Greeting|Response|Rose):\s*', '', greeting, flags=re.I)
    except Exception as e:
        print(f"Error Gemini greeting: {e}")
        return "Hi! Ready?"
    
    print(f"Generated Greeting: {greeting}")
    return greeting if greeting else "Hi! I'm Rose! Ready?"

def generate_greeting_ack_with_gemini(user_greeting_response):
    print("Generating greeting ack...")
    if not gemini_model:
        return "Okay, great!"
    
    prompt = f"You are 'Rose'. Candidate replied to greeting: \"{user_greeting_response}\". Generate 1 brief, positive acknowledgement."
    try:
        response = gemini_model.generate_content(prompt)
        ack = response.text.strip()
        ack = re.sub(r'^"|"$|^(Acknowledgement|Response|Rose):\s*', '', ack, flags=re.I)
    except Exception as e:
        print(f"Error Gemini greeting ack: {e}")
        return "Okay!"
    
    print(f"Generated Greeting Ack: {ack}")
    return ack if ack else "Great!"


# --- Flask Routes (Keep routes as they were in the reverted simple version) ---
@app.route('/')
def index(): session.pop('interview_data', None); return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        flash('No file part.')
        return redirect(url_for('index'))
    
    file = request.files['resume']
    filepath = None

    if file.filename == '':
        flash('No file selected.')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_dir = app.config['UPLOAD_FOLDER']

        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        filepath = os.path.join(upload_dir, filename)

        try:
            file.save(filepath)
            extracted_text = parse_resume(filepath)
            generated_questions = generate_questions_with_gemini(extracted_text)

            if generated_questions and not generated_questions[0].startswith("Error"):
                manager = InterviewManager(questions=generated_questions)
                session['interview_data'] = manager.to_dict()
                print("Setup complete.")
                return redirect(url_for('interview_page'))
            else:
                flash(f"Failed Q-gen: {generated_questions[0] if generated_questions else '?'}")
                return redirect(url_for('index'))

        except (ValueError, FileNotFoundError, PyPDF2Errors.PdfReadError) as parse_err:
            print(f"File processing error: {parse_err}")
            flash(f"Error processing resume: {parse_err}")
            return redirect(url_for('index'))

        except Exception as e:
            print(f"Upload Error: {e}")
            traceback.print_exc()
            flash(f"Error: {e}")
            return redirect(url_for('index'))

        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"Removed: {filepath}")
                except OSError as e:
                    print(f"Error removing {filepath}: {e}")

    else:
        flash('Invalid file type.')
        return redirect(url_for('index'))

@app.route('/interview')
def interview_page():
    if 'interview_data' not in session: flash("No interview found."); return redirect(url_for('index'))
    return render_template('interview.html')

@app.route('/interview/start', methods=['POST'])
def start_interview():
    if 'interview_data' not in session: return jsonify({"error": "No session"}), 400
    try:
        manager_data = session.get('interview_data')
        if not manager_data: return jsonify({"error": "Invalid session data"}), 400
        manager = InterviewManager.from_dict(manager_data); state = manager.get_state()
        if state != "INIT": return jsonify({"error": f"Interview already active (state: {state})"}), 400
        greeting_text = generate_greeting_with_gemini(); audio_filename = tts_interface.text_to_speech(greeting_text, "greeting")
        manager.set_state("AWAITING_GREETING_RESPONSE"); session['interview_data'] = manager.to_dict()
        return jsonify({"status": "OK", "audio_url": url_for('get_audio', filename=audio_filename) if audio_filename else None, "transcript": greeting_text + ("." if not audio_filename else ""), "state": manager.get_state() })
    except Exception as e: print(f"/start Error: {e}"); traceback.print_exc(); return jsonify({"error": f"Server error: {e}"}), 500

@app.route('/interview/next_step', methods=['POST'])
def handle_interview_step(): # Using simpler state logic
    if 'interview_data' not in session: return jsonify({"error": "No session"}), 400
    data = request.get_json(); user_text = data.get('text', '').strip() if data else ""
    try:
        manager = InterviewManager.from_dict(session['interview_data'])
        current_state = manager.get_state()
        audio_filename = None; transcript = ""; is_finished = False; response_data = {}

        if current_state == "AWAITING_GREETING_RESPONSE":
            print(f"Got greeting response: {user_text[:50]}..."); manager.record_greeting_response(user_text)
            ack_text = generate_greeting_ack_with_gemini(user_text)
            transcript = ack_text; audio_filename = tts_interface.text_to_speech(ack_text, "greeting_ack")
            manager.set_state("GREETING_ACKNOWLEDGED")

        elif current_state == "GREETING_ACKNOWLEDGED":
            print("Proceeding to first question..."); q_index = manager.prepare_first_question()
            if q_index is None: return jsonify({"error": "Could not prep first Q"}), 500
            question_text = manager.get_current_question()
            if question_text: transcript = question_text; audio_filename = tts_interface.text_to_speech(question_text, f"question_{q_index}"); manager.set_state("LISTENING")
            else: return jsonify({"error": "Could not get first Q text"}), 500

        elif current_state == "LISTENING":
            print(f"Got answer: {user_text[:50]}..."); manager.set_state("PROCESSING_ANSWER")
            question_asked = manager.get_last_question_asked()
            ack_text, eval_note = evaluate_and_respond_gemini_simple(question_asked, user_text)
            record_result = manager.record_answer_and_evaluation(user_text, eval_note)
            if not record_result: return jsonify({"error": "Failed recording answer"}), 500
            transcript = ack_text; audio_filename = tts_interface.text_to_speech(ack_text, f"ack_{manager.current_question_index}")
            manager.set_state("ACKNOWLEDGED_ANSWER"); print("State -> ACKNOWLEDGED_ANSWER")

        elif current_state == "ACKNOWLEDGED_ANSWER":
            print("Acknowledged answer, preparing next question.");
            next_q_result = manager.prepare_next_question()
            if not next_q_result: return jsonify({"error": "Failed preparing next Q"}), 500
            next_state = next_q_result.get("state")
            if next_state == "ASKING_QUESTION":
                question_text = manager.get_current_question()
                if question_text: transcript = question_text; audio_filename = tts_interface.text_to_speech(question_text, f"question_{manager.current_question_index}"); manager.set_state("LISTENING")
                else: return jsonify({"error": "Could not get next Q text"}), 500
            elif next_state == "CLOSING":
                closing_text = "Okay, that was the last question. Thanks for your time! The report is being generated."
                transcript = closing_text; audio_filename = tts_interface.text_to_speech(closing_text, "closing")
                manager.set_state("FINISHED"); is_finished = True
            else: return jsonify({"error": f"Unexpected state after prep next: {next_state}"}), 500
        else: print(f"Warning: Request in unexpected state: {current_state}"); return jsonify({"error": f"Unexpected state: {current_state}"}), 400

        session['interview_data'] = manager.to_dict()
        response_data = { "status": "OK", "audio_url": url_for('get_audio', filename=audio_filename) if audio_filename else None, "transcript": transcript, "state": manager.get_state(), "is_finished": is_finished }
        if transcript and not audio_filename and tts_interface.ENABLE_HF_TTS: response_data["transcript"] += " (Audio unavailable)"
        return jsonify(response_data)
    except Exception as e: print(f"Error in /next_step: {e}"); traceback.print_exc(); return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/audio/<path:filename>')
def get_audio(filename):
    directory = os.path.abspath(app.config['TTS_AUDIO_FOLDER']); safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename: return jsonify({"error": "Invalid fn"}), 400
    try: return send_from_directory(directory, safe_filename, as_attachment=False)
    except FileNotFoundError: return jsonify({"error": "Audio not found"}), 404
    except Exception as e: print(f"Audio serve error: {e}"); return jsonify({"error": "Server error"}), 500

@app.route('/report')
def report_page():
    manager_data = session.get('interview_data')
    if not manager_data:
        flash("No interview data for report.")
        return redirect(url_for('index'))
    
    try:
        manager = InterviewManager.from_dict(manager_data)

        if manager.get_state() not in ["CLOSING", "FINISHED"]:
            flash("Interview not completed yet.")
            return redirect(url_for('interview_page'))
        
        session.pop('interview_data', None)
        final_data = manager.get_final_data()

        if not final_data:
            flash("Could not retrieve final report data.")
            return redirect(url_for('index'))

        return render_template('report.html', report=final_data, WEASYPRINT_AVAILABLE=WEASYPRINT_AVAILABLE)

    except Exception as e:
        print(f"Report page error: {e}")
        traceback.print_exc()
        flash("Error generating report.")
        return redirect(url_for('index'))

@app.route('/download_report')
def download_report():
    manager_data = session.get('interview_data')
    if not manager_data:
        flash("Session expired for download.")
        return redirect(url_for('index'))
    
    if not WEASYPRINT_AVAILABLE:
        flash("PDF generation unavailable.")
        return redirect(url_for('report_page', _anchor='download_unavailable'))
    
    try:
        manager = InterviewManager.from_dict(manager_data)

        if manager.get_state() not in ["CLOSING", "FINISHED"]:
            flash("Interview not complete.")
            return redirect(url_for('interview_page'))
        
        final_data = manager.get_final_data()

        if not final_data:
            flash("Could not get data for PDF.")
            return redirect(url_for('report_page'))
        
        html_string = render_template('report.html', report=final_data, is_pdf_render=True, WEASYPRINT_AVAILABLE=True)
        pdf_bytes = weasyprint.HTML(string=html_string).write_pdf()
        
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=interview_report.pdf'

        print("Generated and sending PDF report.")
        return response

    except Exception as e:
        print(f"Error generating PDF: {e}")
        traceback.print_exc()
        flash("Failed PDF generation.")
        return redirect(url_for('report_page'))

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Flask dev server...")
    app.run(debug=True, host='0.0.0.0', port=5000)