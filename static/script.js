document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('editor');
    const tooltip = document.getElementById('tooltip');
    let debounceTimer;

    // --- Debouncing and Input Handling ---

    const handleInput = () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const text = editor.innerText;
            if (text.trim().length > 0) {
                checkGrammar(text);
            } else {
                clearHighlights(); // Clear highlights if editor is empty
            }
        }, 1000); // 1-second delay
    };

    editor.addEventListener('input', handleInput);

    // --- API Communication ---

    async function checkGrammar(text) {
        try {
            const response = await fetch('/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                console.error('API Error:', errorData.error);
                // Optionally, display a subtle error to the user
                return;
            }

            const matches = await response.json();
            applyHighlights(matches);
        } catch (error) {
            console.error('Network or fetch error:', error);
        }
    }

    // --- Highlighting Logic ---

    function clearHighlights() {
        const errors = editor.querySelectorAll('.grammar-error');
        errors.forEach(errorSpan => {
            // Replace the span with its own text content (unwrapping it)
            const parent = errorSpan.parentNode;
            while (errorSpan.firstChild) {
                parent.insertBefore(errorSpan.firstChild, errorSpan);
            }
            parent.removeChild(errorSpan);
        });
        // Normalize the DOM to merge adjacent text nodes
        editor.normalize();
    }

    function applyHighlights(matches) {
        const selection = window.getSelection();
        const anchorNode = selection.anchorNode;
        const anchorOffset = selection.anchorOffset;

        clearHighlights();

        if (matches.length === 0) return;

        // Sort matches in reverse to avoid offset issues while modifying the DOM
        matches.sort((a, b) => b.offset - a.offset);

        matches.forEach(match => {
            const range = findTextRange(editor, match.offset, match.errorLength);
            if (range) {
                const span = document.createElement('span');
                span.className = 'grammar-error';
                span.dataset.message = match.message;
                span.dataset.replacements = match.replacements.join(', ');

                try {
                    range.surroundContents(span);
                } catch (e) {
                    console.error('Could not surround contents for match:', match, e);
                }
            }
        });

        // Restore cursor position
        if (anchorNode) {
            try {
                const newRange = document.createRange();
                newRange.setStart(anchorNode, anchorOffset);
                newRange.collapse(true);
                selection.removeAllRanges();
                selection.addRange(newRange);
            } catch (e) {
                console.error("Failed to restore selection", e);
            }
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


    // --- Tooltip Logic ---

    let currentErrorSpan = null;

    editor.addEventListener('mouseover', (event) => {
        const target = event.target;
        if (target.classList.contains('grammar-error')) {
            if (target === currentErrorSpan) return; // Avoid flickering
            currentErrorSpan = target;

            // Populate and position the tooltip
            tooltip.innerHTML = `<strong>${target.dataset.message}</strong><br>Suggestions: <em>${target.dataset.replacements || 'none'}</em>`;

            const rect = target.getBoundingClientRect();
            tooltip.style.left = `${rect.left}px`;
            tooltip.style.top = `${rect.bottom + 5}px`;

            tooltip.classList.remove('hidden');
            tooltip.classList.add('visible');
        }
    });

    editor.addEventListener('mouseout', (event) => {
        const target = event.target;
        if (target.classList.contains('grammar-error')) {
            currentErrorSpan = null;
            hideTooltip();
        }
    });

    function hideTooltip() {
        tooltip.classList.remove('visible');
    }

    // Set initial focus to the editor
    editor.focus();
});
