from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import language_tool_python

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Use the LanguageTool Public API. This avoids the large local download.
try:
    # We can specify a language, e.g., 'en-US'
    tool = language_tool_python.LanguageToolPublicAPI('en-US')
    print("Successfully connected to LanguageTool Public API.")
except Exception as e:
    print(f"Error initializing LanguageToolPublicAPI: {e}")
    tool = None

@app.route('/')
def index():
    """Serves the main HTML page for the text editor."""
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_text():
    if not tool:
        return jsonify({"error": "LanguageTool API is not available."}), 500

    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided."}), 400

    text = data.get('text')

    try:
        matches = tool.check(text)
    except language_tool_python.utils.RateLimitError:
        # Return a specific error for rate limiting
        return jsonify({"error": "Rate limit exceeded. Please wait a moment before trying again."}), 429
    except Exception as e:
        # Return a generic error for other issues
        return jsonify({"error": "An unexpected error occurred while checking grammar.", "details": str(e)}), 500

    # Convert Match objects to a list of dictionaries to be JSON serializable
    results = [
        {
            'offset': match.offset,
            'errorLength': match.errorLength,
            'category': match.category,
            'ruleId': match.ruleId,
            'message': match.message,
            'replacements': match.replacements,
            'context': match.context,
            'sentence': match.sentence,
        } for match in matches
    ]

    return jsonify(results)

if __name__ == '__main__':
    # Running on port 5001 to avoid potential conflicts.
    # Host '0.0.0.0' makes it accessible from the network.
    app.run(host='0.0.0.0', port=5001, debug=True)
