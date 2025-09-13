from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import language_tool_python
import os
import threading
import nltk
from nltk.corpus import wordnet

app = Flask(__name__)
CORS(app)

# --- Global Server State ---
tool = None
tool_lock = threading.Lock() # To prevent race conditions during server restarts

def download_nltk_data():
    """Downloads required NLTK data models if not already present."""
    required_packages = ['wordnet', 'punkt', 'averaged_perceptron_tagger']
    for package in required_packages:
        try:
            nltk.data.find(f'tokenizers/{package}' if package == 'punkt' else f'corpora/{package}')
        except LookupError:
            print(f"NLTK data package '{package}' not found. Downloading...")
            nltk.download(package, quiet=True)
            print(f"'{package}' downloaded.")

def start_lt_server():
    """Initializes or restarts the LanguageTool server."""
    global tool
    print("Initializing local LanguageTool server...")
    try:
        if 'LTP_JAR_DIR_PATH' not in os.environ:
            print("INFO: LTP_JAR_DIR_PATH environment variable not set.")
            print("INFO: The app will try to use the default cached server if available.")

        new_tool = language_tool_python.LanguageTool('en-US')
        new_tool.picky = True
        tool = new_tool
        print("Local LanguageTool server initialized successfully in Picky mode.")
    except Exception as e:
        print(f"FATAL: Failed to initialize local LanguageTool server: {e}")
        tool = None

# --- Initial Server & Data Startup ---
download_nltk_data()
start_lt_server()


@app.route('/')
def index():
    """Serves the main HTML page for the text editor."""
    return render_template('index.html')

@app.route('/word_tools', methods=['POST'])
def word_tools():
    """Provides synonyms and definitions for a given word."""
    data = request.get_json()
    word = data.get('word', '').lower()
    if not word:
        return jsonify({"error": "No word provided."}), 400

    synonyms = set()
    definitions = []

    synsets = wordnet.synsets(word)
    if synsets:
        for syn in synsets:
            # Add definition
            definitions.append(f"({syn.pos()}) {syn.definition()}")
            # Add synonyms
            for lemma in syn.lemmas():
                syn_word = lemma.name().replace('_', ' ')
                if syn_word != word:
                    synonyms.add(syn_word)

    return jsonify({
        "word": word,
        "synonyms": sorted(list(synonyms)),
        "definitions": definitions
    })


@app.route('/check', methods=['POST'])
def check_text():
    """Handles grammar check requests with a self-healing mechanism."""
    with tool_lock:
        if tool is None or not tool._server_is_alive():
            print("Server process not detected. Attempting to restart...")
            if tool:
                tool.close()
            start_lt_server()

        if not tool:
            error_message = "LanguageTool server is not running and could not be restarted."
            return jsonify({"error": error_message}), 503

    data = request.get_json()
    text = data.get('text', '')
    language = data.get('language', 'en-US')

    try:
        tool.language = language
        matches = tool.check(text)
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred during grammar check.", "details": str(e)}), 500

    def get_error_type(category: str) -> str:
        if category in ['TYPOS']: return 'Spelling'
        if category in ['GRAMMAR', 'CASING', 'CAPITALIZATION', 'PUNCTUATION', 'CONFUSED_WORDS', 'SEMANTICS', 'SYNTAX']: return 'Grammar'
        if category in ['STYLE', 'REDUNDANCY', 'TYPOGRAPHY', 'CLARITY', 'MISC']: return 'Style'
        return category.title()

    results = []
    for m in matches:
        match_dict = {k: v for k, v in m.__dict__.items() if not k.startswith('_')}
        match_dict['type'] = get_error_type(m.category)
        results.append(match_dict)

    def calculate_analytics(text: str, current_results: list) -> dict:
        word_count = len(text.strip().split())
        if word_count == 0:
            return {"wordCount": 0, "overallScore": 100, "correctnessScore": 100, "clarityScore": 100, "styleScore": 100}

        errors_per_100_words = (len(current_results) / word_count) * 100
        overall_score = max(0, 100 - round(errors_per_100_words * 2))

        correctness_errors = sum(1 for r in current_results if r['type'] in ['Spelling', 'Grammar'])
        clarity_errors = sum(1 for r in current_results if r['type'] == 'Clarity')
        style_errors = sum(1 for r in current_results if r['type'] == 'Style')

        correctness_score = max(0, 100 - round(((correctness_errors / word_count) * 100) * 5))
        clarity_score = max(0, 100 - round(((clarity_errors / word_count) * 100) * 5))
        style_score = max(0, 100 - round(((style_errors / word_count) * 100) * 5))

        return {
            "wordCount": word_count, "overallScore": overall_score, "correctnessScore": correctness_score,
            "clarityScore": clarity_score, "styleScore": style_score,
        }

    analytics = calculate_analytics(text, results)

    return jsonify({"matches": results, "analytics": analytics})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
