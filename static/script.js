document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const editor = document.getElementById('editor');
    const tooltip = document.getElementById('tooltip');
    const errorList = document.getElementById('error-list');
    const wordCountEl = document.getElementById('word-count');

    let debounceTimer;

    // --- Debouncing and Input Handling ---
    const handleInput = () => {
        clearTimeout(debounceTimer);
        const text = editor.innerText;
        updateWordCount(text);

        debounceTimer = setTimeout(() => {
            if (text.trim().length > 0) {
                checkGrammar(text);
            } else {
                clearHighlights();
                errorList.innerHTML = '<p class="placeholder-text">No errors detected.</p>';
            }
        }, 1000); // 1-second delay
    };

    editor.addEventListener('input', handleInput);

    // --- Word Count ---
    function updateWordCount(text) {
        const words = text.trim().split(/\s+/).filter(word => word.length > 0);
        wordCountEl.textContent = `Words: ${words.length}`;
    }

    // --- API Communication ---
    async function checkGrammar(text) {
        try {
            const response = await fetch('/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                console.error('API Error:', errorData.error);
                errorList.innerHTML = `<p class="placeholder-text error-message">API Error: ${errorData.error}</p>`;
                return;
            }

            const matches = await response.json();
            applyHighlights(matches);
            displayErrorsInSidebar(matches);
        } catch (error) {
            console.error('Network or fetch error:', error);
            errorList.innerHTML = '<p class="placeholder-text error-message">Could not connect to server.</p>';
        }
    }

    // --- Highlighting Logic ---
    function clearHighlights() {
        const errors = editor.querySelectorAll('.grammar-error');
        errors.forEach(errorSpan => {
            const parent = errorSpan.parentNode;
            while (errorSpan.firstChild) {
                parent.insertBefore(errorSpan.firstChild, errorSpan);
            }
            parent.removeChild(errorSpan);
        });
        editor.normalize();
    }

    function applyHighlights(matches) {
        const selection = window.getSelection();
        const anchorNode = selection.anchorNode;
        const anchorOffset = selection.anchorOffset;

        clearHighlights();
        if (matches.length === 0) return;

        matches.sort((a, b) => b.offset - a.offset);

        matches.forEach(match => {
            const range = findTextRange(editor, match.offset, match.errorLength);
            if (range) {
                const span = document.createElement('span');
                span.className = 'grammar-error';
                span.dataset.message = match.message;
                span.dataset.replacements = match.replacements.join(', ');
                span.dataset.offset = match.offset; // Store offset for click-to-highlight
                try {
                    range.surroundContents(span);
                } catch (e) {
                    console.error('Could not surround contents for match:', match, e);
                }
            }
        });

        if (anchorNode) {
            try {
                const newRange = document.createRange();
                newRange.setStart(anchorNode, anchorOffset);
                newRange.collapse(true);
                selection.removeAllRanges();
                selection.addRange(newRange);
            } catch (e) { console.error("Failed to restore selection", e); }
        }
    }

    function findTextRange(root, start, length) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
        let charCount = 0;
        let startNode, endNode, startOffset, endOffset;
        while (walker.nextNode()) {
            const node = walker.currentNode;
            const nodeLength = node.nodeValue.length;
            if (charCount <= start && charCount + nodeLength > start) {
                startNode = node;
                startOffset = start - charCount;
            }
            if (charCount < start + length && charCount + nodeLength >= start + length) {
                endNode = node;
                endOffset = start + length - charCount;
                break;
            }
            charCount += nodeLength;
        }
        if (startNode && endNode) {
            const range = document.createRange();
            range.setStart(startNode, startOffset);
            range.setEnd(endNode, endOffset);
            return range;
        }
        return null;
    }

    // --- Sidebar and Tooltip Logic ---
    function displayErrorsInSidebar(matches) {
        errorList.innerHTML = ''; // Clear previous errors
        if (matches.length === 0) {
            errorList.innerHTML = '<p class="placeholder-text">No errors detected. Good job!</p>';
            return;
        }
        matches.sort((a, b) => a.offset - b.offset); // Sort by position in text
        matches.forEach(match => {
            const card = document.createElement('div');
            card.className = 'error-card';
            card.dataset.offset = match.offset;
            card.innerHTML = `
                <div class="error-card-header type-${match.type.toLowerCase()}">${match.type}</div>
                <div class="error-card-body">
                    <p>${match.message}</p>
                    ${match.replacements.length > 0 ? `<strong>Suggestion:</strong> <em>${match.replacements[0]}</em>` : ''}
                </div>
            `;
            errorList.appendChild(card);
        });
    }

    errorList.addEventListener('click', (event) => {
        const card = event.target.closest('.error-card');
        if (card) {
            const offset = card.dataset.offset;
            const errorSpan = editor.querySelector(`.grammar-error[data-offset="${offset}"]`);
            if (errorSpan) {
                errorSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
                // Flash highlight
                errorSpan.style.transition = 'background-color 0.1s ease';
                errorSpan.style.backgroundColor = 'rgba(254, 107, 107, 0.5)';
                setTimeout(() => {
                    errorSpan.style.backgroundColor = '';
                }, 500);
            }
        }
    });

    // Tooltip logic remains the same
    editor.addEventListener('mouseover', (event) => {
        const target = event.target;
        if (target.classList.contains('grammar-error')) {
            tooltip.innerHTML = `<strong>${target.dataset.message}</strong><br>Suggestions: <em>${target.dataset.replacements || 'none'}</em>`;
            const rect = target.getBoundingClientRect();
            tooltip.style.left = `${rect.left}px`;
            tooltip.style.top = `${rect.bottom + 5}px`;
            tooltip.classList.remove('hidden');
            tooltip.classList.add('visible');
        }
    });
    editor.addEventListener('mouseout', (event) => {
        if (event.target.classList.contains('grammar-error')) {
            tooltip.classList.remove('visible');
        }
    });

    // --- Initial State ---
    editor.focus();
    updateWordCount('');
    errorList.innerHTML = '<p class="placeholder-text">Start typing to see suggestions.</p>';
});
