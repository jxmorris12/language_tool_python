from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import language_tool_python
import os
import threading
import nltk
from nltk.corpus import wordnet
from concurrent.futures import ThreadPoolExecutor, TimeoutError

app = Flask(__name__)
CORS(app)

# --- Global Server State ---
tool = None
tool_lock = threading.Lock() # To prevent race conditions during server restarts
# A single-threaded executor to ensure only one check runs at a time against the single LanguageTool instance.
executor = ThreadPoolExecutor(max_workers=1)

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
    """Handles grammar check requests with a timeout and self-healing mechanism."""
    # Grab a handle to the current tool instance under a lock to ensure it's valid at this moment.
    with tool_lock:
        if tool is None or not tool._server_is_alive():
            print("Server process not detected or unresponsive. Attempting to restart...")
            if tool:
                tool.close()  # Clean up the old instance if it exists
            start_lt_server()

        if not tool:
            error_message = "LanguageTool server is not running and could not be restarted."
            return jsonify({"error": error_message}), 503  # Service Unavailable

        current_tool = tool

    data = request.get_json()
    text = data.get('text', '')

    # Define the check function to be run in the executor.
    # It uses the 'current_tool' handle we safely acquired.
    def run_check():
        current_tool.language = data.get('language', 'en-US')
        current_tool.disabled_rules = set(data.get('disabled_rules', []))
        current_tool.disabled_categories = set(data.get('disabled_categories', []))
        return current_tool.check(text)

    future = executor.submit(run_check)

    try:
        # Set a 10-second timeout for the grammar check.
        matches = future.result(timeout=10.0)
    except TimeoutError:
        print("ERROR: Grammar check timed out. The LanguageTool server is likely hung.")
        # If the check times out, the server is compromised. Restart it for the next request.
        with tool_lock:
            print("Attempting to restart the LanguageTool server after timeout...")
            # Check if the global tool is the same one that timed out.
            # Another request might have already restarted it.
            if tool is current_tool:
                tool.close()
                start_lt_server()
        return jsonify({"error": "The grammar check took too long to complete and was aborted."}), 504
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during grammar check: {e}")
        # For other unexpected errors, a restart is also a safe bet.
        with tool_lock:
            if tool is current_tool and not tool._server_is_alive():
                 print("Restarting server after unexpected error.")
                 tool.close()
                 start_lt_server()
        return jsonify({"error": "An unexpected error occurred during grammar check.", "details": str(e)}), 500

    # Convert Match objects to a list of dictionaries to be JSON serializable
    results = [
        {k: v for k, v in m.__dict__.items() if not k.startswith('_')}
        for m in matches
    ]

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
