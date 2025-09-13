document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const editor = document.getElementById('editor');
    const errorList = document.getElementById('error-list');
    const wordCountEl = document.getElementById('word-count');

    // Analytics Panel Elements
    const overallScoreEl = document.getElementById('overall-score');
    const correctnessBarEl = document.getElementById('correctness-bar');
    const clarityBarEl = document.getElementById('clarity-bar');
    const styleBarEl = document.getElementById('style-bar');

    // Filter Controls
    const filterControls = document.getElementById('filter-controls');

    let debounceTimer;
    let lastMatches = []; // Store the last set of matches for filtering
    let currentFilter = 'All'; // Default filter

    // --- Utility to escape HTML ---
    function escapeHtml(unsafe) {
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // --- Input Handling ---
    const handleInput = () => {
        clearTimeout(debounceTimer);
        const text = editor.innerText;

        debounceTimer = setTimeout(() => {
            if (text.trim().length > 0) {
                checkGrammar(text);
            } else {
                resetUI();
            }
        }, 1000);
    };

    editor.addEventListener('input', handleInput);

    // --- Reset UI State ---
    function resetUI() {
        lastMatches = [];
        editor.innerHTML = '';
        errorList.innerHTML = '<p class="placeholder-text">Start typing to see suggestions.</p>';
        updateAnalyticsPanel({ wordCount: 0, overallScore: 100, correctnessScore: 100, clarityScore: 100, styleScore: 100 });
    }

    // --- API Communication & Main Rendering Call ---
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

            const data = await response.json();
            lastMatches = data.matches || [];

            updateAnalyticsPanel(data.analytics);
            displayErrorsInSidebar(); // Renders based on lastMatches and currentFilter
            applyHighlights(lastMatches, text);
        } catch (error) {
            console.error('Network or fetch error:', error);
            errorList.innerHTML = '<p class="placeholder-text error-message">Could not connect to server.</p>';
        }
    }

    // --- Analytics Panel & Score Logic ---
    function updateAnalyticsPanel(analytics) {
        if (!analytics) return;
        wordCountEl.textContent = `Words: ${analytics.wordCount}`;
        overallScoreEl.textContent = analytics.overallScore;
        correctnessBarEl.style.width = `${analytics.correctnessScore}%`;
        clarityBarEl.style.width = `${analytics.clarityScore}%`;
        styleBarEl.style.width = `${analytics.styleScore}%`;
    }

    // --- Highlighting Logic ---
    function applyHighlights(matches, text) {
        if (!matches) return;

        const selection = window.getSelection();
        const anchorNode = selection.anchorNode;
        const anchorOffset = selection.anchorOffset;

        // Rebuild HTML to apply highlights
        matches.sort((a, b) => a.offset - b.offset);
        let newHtml = '';
        let lastIndex = 0;
        matches.forEach(match => {
            newHtml += escapeHtml(text.substring(lastIndex, match.offset));
            const errorText = escapeHtml(text.substring(match.offset, match.offset + match.errorLength));
            const message = escapeHtml(match.message);
            newHtml += `<span class="grammar-error" data-message="${message}" data-offset="${match.offset}">${errorText}</span>`;
            lastIndex = match.offset + match.errorLength;
        });
        newHtml += escapeHtml(text.substring(lastIndex));
        editor.innerHTML = newHtml.replace(/\n/g, '<br>');

        // Restore cursor position (best effort)
        // This is complex and may not work perfectly after innerHTML change.
        if (anchorNode) {
            try {
                const newRange = document.createRange();
                // This part is simplified and might not be accurate
                newRange.setStart(editor.firstChild || editor, 0);
                newRange.collapse(true);
                selection.removeAllRanges();
                selection.addRange(newRange);
            } catch (e) { console.error("Failed to restore selection", e); }
        }
    }

    // --- Sidebar Logic ---
    function displayErrorsInSidebar() {
        errorList.innerHTML = '';
        const filteredMatches = lastMatches.filter(match =>
            currentFilter === 'All' || match.type === currentFilter
        );

        if (filteredMatches.length === 0) {
            const message = currentFilter === 'All' ? 'No errors detected. Good job!' : `No ${currentFilter} errors.`;
            errorList.innerHTML = `<p class="placeholder-text">${message}</p>`;
            return;
        }

        filteredMatches.forEach(match => {
            const card = document.createElement('div');
            card.className = 'error-card';
            card.dataset.offset = match.offset;
            card.dataset.type = match.type;
            card.innerHTML = `
                <div class="error-card-header type-${match.type.toLowerCase()}">${match.type}</div>
                <div class="error-card-body">
                    <p>${escapeHtml(match.message)}</p>
                    ${match.replacements.length > 0 ? `<strong>Suggestion:</strong> <em>${escapeHtml(match.replacements[0])}</em>` : ''}
                </div>
            `;
            errorList.appendChild(card);
        });
    }

    // --- Event Listeners for Interaction ---
    filterControls.addEventListener('click', (event) => {
        const target = event.target;
        if (target.classList.contains('filter-btn')) {
            filterControls.querySelector('.active').classList.remove('active');
            target.classList.add('active');
            currentFilter = target.dataset.filter;
            displayErrorsInSidebar(); // Re-render the list with the new filter
        }
    });

    errorList.addEventListener('click', (event) => {
        const card = event.target.closest('.error-card');
        if (card) {
            const offset = card.dataset.offset;
            const errorSpan = editor.querySelector(`.grammar-error[data-offset="${offset}"]`);
            if (errorSpan) {
                errorSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
                errorSpan.style.transition = 'background-color 0.1s ease';
                errorSpan.style.backgroundColor = 'rgba(254, 107, 107, 0.5)';
                setTimeout(() => { errorSpan.style.backgroundColor = ''; }, 500);
            }
        }
    });

    // --- Initial State ---
    resetUI();
    editor.focus();
});
