from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import typerfect
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
    """
    Downloads required NLTK data models to a local project folder
    to prevent re-downloading on every server restart.
    """
    local_nltk_dir = os.path.join(os.path.dirname(__file__), 'nltk_data')
    os.makedirs(local_nltk_dir, exist_ok=True)

    if local_nltk_dir not in nltk.data.path:
        nltk.data.path.append(local_nltk_dir)

    required_packages = ['wordnet', 'punkt', 'averaged_perceptron_tagger']
    for package in required_packages:
        try:
            package_path = f'tokenizers/{package}' if package == 'punkt' else f'corpora/{package}'
            nltk.data.find(package_path)
        except LookupError:
            print(f"NLTK data package '{package}' not found. Downloading to '{local_nltk_dir}'...")
            nltk.download(package, download_dir=local_nltk_dir, quiet=True)
            print(f"'{package}' downloaded.")

def start_lt_server():
    """Initializes or restarts the LanguageTool server."""
    global tool
    print("Initializing local LanguageTool server...")
    try:
        if 'LTP_JAR_DIR_PATH' not in os.environ:
            print("INFO: LTP_JAR_DIR_PATH environment variable not set.")
            print("INFO: The app will try to use the default cached server if available.")

        new_tool = typerfect.LanguageTool('en-US')
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
            definitions.append(f"({syn.pos()}) {syn.definition()}")
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
        # Set user-defined controls for this specific check
        tool.disabled_rules = set(data.get('disabled_rules', []))
        tool.disabled_categories = set(data.get('disabled_categories', []))
        matches = tool.check(text)
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred during grammar check.", "details": str(e)}), 500

    # Convert Match objects to a list of dictionaries to be JSON serializable
    results = []
    for m in matches:
        match_dict = {k: v for k, v in m.__dict__.items() if not k.startswith('_')}
        results.append(match_dict)

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
