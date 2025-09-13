from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import language_tool_python
import os

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Offline Mode Setup ---
# The application will now use the local LanguageTool server.
# The user must set the LTP_JAR_DIR_PATH environment variable
# to the location of the unzipped LanguageTool server files.
tool = None
try:
    # Check if the environment variable is set.
    # The library itself will use this path.
    if 'LTP_JAR_DIR_PATH' not in os.environ:
        print("INFO: LTP_JAR_DIR_PATH environment variable not set.")
        print("INFO: The app will try to use the default cached server if available.")
        # We can let it proceed, it will either find a cached version or fail,
        # which is better than crashing the whole app on startup.

    print("Initializing local LanguageTool server...")
    tool = language_tool_python.LanguageTool('en-US')
    print("Local LanguageTool server initialized successfully.")

except Exception as e:
    print(f"FATAL: Failed to initialize local LanguageTool server: {e}")
    print("FATAL: Please ensure Java is installed and the LTP_JAR_DIR_PATH environment variable is set correctly.")
    # The tool will remain None, and the API will return an error.

@app.route('/')
def index():
    """Serves the main HTML page for the text editor."""
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_text():
    if not tool:
        error_message = (
            "LanguageTool server is not running. "
            "Please check the server logs. Ensure Java is installed and the "
            "LTP_JAR_DIR_PATH environment variable is set to your LanguageTool folder."
        )
        return jsonify({"error": error_message}), 503 # Service Unavailable

    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided."}), 400

    text = data.get('text')

    try:
        matches = tool.check(text)
    except Exception as e:
        # Catch other potential errors during checking
        return jsonify({"error": "An unexpected error occurred while checking grammar.", "details": str(e)}), 500

    # --- Helper function to categorize errors ---
    def get_error_type(category: str) -> str:
        """Maps raw LanguageTool categories to user-friendly types."""
        # This mapping can be expanded based on the full list of LT categories
        if category in ['TYPOS']:
            return 'Spelling'
        elif category in [
            'GRAMMAR', 'CASING', 'CAPITALIZATION', 'PUNCTUATION',
            'CONFUSED_WORDS', 'SEMANTICS', 'SYNTAX'
        ]:
            return 'Grammar'
        elif category in [
            'STYLE', 'REDUNDANCY', 'TYPOGRAPHY', 'CLARITY', 'MISC'
        ]:
            return 'Style'
        else:
            # For any other categories, we can see them as they come up
            return category.title()

    # Convert Match objects to a list of dictionaries to be JSON serializable
    results = [
        {
            'type': get_error_type(match.category),
            'message': match.message,
            'replacements': match.replacements,
            'offset': match.offset,
            'errorLength': match.errorLength,
            'context': match.context,
            'sentence': match.sentence,
            'category': match.category,
            'ruleId': match.ruleId
        } for match in matches
    ]

    return jsonify(results)

if __name__ == '__main__':
    # Running on port 5001 to avoid potential conflicts.
    # Host '0.0.0.0' makes it accessible from the network.
    app.run(host='0.0.0.0', port=5001, debug=True)
