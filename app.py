from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import language_tool_python
import os
import threading

app = Flask(__name__)
CORS(app)

# --- Global Server State ---
tool = None
tool_lock = threading.Lock() # To prevent race conditions during server restarts

def start_lt_server():
    """Initializes or restarts the LanguageTool server."""
    global tool
    print("Initializing local LanguageTool server...")
    try:
        if 'LTP_JAR_DIR_PATH' not in os.environ:
            print("INFO: LTP_JAR_DIR_PATH environment variable not set.")
            print("INFO: The app will try to use the default cached server if available.")

        new_tool = language_tool_python.LanguageTool('en-US')
        new_tool.picky = True  # Enable stricter, more comprehensive checking
        tool = new_tool
        print("Local LanguageTool server initialized successfully in Picky mode.")
    except Exception as e:
        print(f"FATAL: Failed to initialize local LanguageTool server: {e}")
        print("FATAL: Please ensure Java is installed and the LTP_JAR_DIR_PATH environment variable is set correctly.")
        tool = None # Ensure tool is None on failure

# --- Initial Server Startup ---
start_lt_server()


@app.route('/')
def index():
    """Serves the main HTML page for the text editor."""
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_text():
    """Handles grammar check requests with a self-healing mechanism."""
    with tool_lock:
        # Self-healing: Check if the server is alive, restart if not.
        # The `_server` attribute is internal, but necessary for this check.
        if tool is None or not tool._server_is_alive():
            print("Server process not detected. Attempting to restart...")
            if tool:
                tool.close() # Attempt to clean up the old instance
            start_lt_server()

        if not tool:
            error_message = (
                "LanguageTool server is not running and could not be restarted. "
                "Please check the server logs. Ensure Java is installed and the "
                "LTP_JAR_DIR_PATH environment variable is set correctly."
            )
            return jsonify({"error": error_message}), 503

    # Proceed with the check using the (potentially new) tool instance
    data = request.get_json()
    text = data.get('text', '')
    language = data.get('language', 'en-US')

    try:
        tool.language = language
        matches = tool.check(text)
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred while checking grammar.", "details": str(e)}), 500

    # --- Analytics and Response Formatting ---
    def get_error_type(category: str) -> str:
        if category in ['TYPOS']: return 'Spelling'
        if category in ['GRAMMAR', 'CASING', 'CAPITALIZATION', 'PUNCTUATION', 'CONFUSED_WORDS', 'SEMANTICS', 'SYNTAX']: return 'Grammar'
        if category in ['STYLE', 'REDUNDANCY', 'TYPOGRAPHY', 'CLARITY', 'MISC']: return 'Style'
        return category.title()

    results = [{'type': get_error_type(m.category), **m.__dict__} for m in matches]

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
