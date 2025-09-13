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

    // Controls
    const filterControls = document.getElementById('filter-controls');
    const languageSwitch = document.getElementById('language-switch');
    const fontSelect = document.getElementById('font-select');

    // Context Menu Elements
    const contextMenu = document.getElementById('context-menu');
    const thesaurusResultsEl = document.getElementById('thesaurus-results');
    const dictionaryResultsEl = document.getElementById('dictionary-results');

    // --- State Variables ---
    let debounceTimer;
    let lastMatches = [];
    let currentFilter = 'All';
    let currentLanguage = 'en-US';

    // --- Utility to escape HTML ---
    function escapeHtml(unsafe) {
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // --- Input Handling ---
    const handleInput = () => {
        clearTimeout(debounceTimer);
        const currentText = editor.innerText;
        updateWordCount(currentText);
        debounceTimer = setTimeout(() => {
            const finalText = editor.innerText;
            if (finalText.trim().length > 0) {
                checkGrammar(finalText);
            } else {
                resetUI();
            }
        }, 800);
    };
    editor.addEventListener('input', handleInput);
    editor.addEventListener('paste', handleInput);

    // --- Reset UI State ---
    function resetUI() {
        lastMatches = [];
        editor.innerHTML = '';
        errorList.innerHTML = '<p class="placeholder-text">Start typing to see suggestions.</p>';
        updateAnalyticsPanel({ wordCount: 0, overallScore: 100, correctnessScore: 100, clarityScore: 100, styleScore: 100 });
    }

    // --- Word Count ---
    function updateWordCount(text) {
        const words = text.trim().split(/\s+/).filter(word => word.length > 0);
        wordCountEl.textContent = `Words: ${words.length}`;
    }

    // --- API Communication ---
    async function checkGrammar(text) {
        if (text.trim() === '') return;
        try {
            const response = await fetch('/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text, language: currentLanguage }),
            });
            if (!response.ok) {
                const errorData = await response.json();
                errorList.innerHTML = `<p class="placeholder-text error-message">API Error: ${errorData.error}</p>`;
                return;
            }
            const data = await response.json();
            lastMatches = data.matches || [];
            updateAnalyticsPanel(data.analytics);
            applyHighlights(lastMatches, text);
        } catch (error) {
            console.error('Network or fetch error:', error);
            errorList.innerHTML = '<p class="placeholder-text error-message">Could not connect to server.</p>';
        }
    }

    async function fetchWordTools(word) {
        try {
            const response = await fetch('/word_tools', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word: word }),
            });
            if (!response.ok) return;
            const data = await response.json();
            populateContextMenu(data);
        } catch (error) {
            console.error('Word tools fetch error:', error);
        }
    }

    // --- UI Rendering ---
    function updateAnalyticsPanel(analytics) {
        if (!analytics) return;
        overallScoreEl.textContent = analytics.overallScore;
        correctnessBarEl.style.width = `${analytics.correctnessScore}%`;
        clarityBarEl.style.width = `${analytics.clarityScore}%`;
        styleBarEl.style.width = `${analytics.styleScore}%`;
    }

    function applyHighlights(matches, text) {
        displayErrorsInSidebar();
        if (!matches) return;
        let cursorPosition = saveCursorPosition();
        matches.sort((a, b) => a.offset - b.offset);
        let newHtml = '';
        let lastIndex = 0;
        matches.forEach(match => {
            newHtml += escapeHtml(text.substring(lastIndex, match.offset));
            const errorText = escapeHtml(text.substring(match.offset, match.offset + match.errorLength));
            newHtml += `<span class="grammar-error" data-offset="${match.offset}">${errorText}</span>`;
            lastIndex = match.offset + match.errorLength;
        });
        newHtml += escapeHtml(text.substring(lastIndex));
        editor.innerHTML = newHtml.replace(/\n/g, '<br>');
        restoreCursorPosition(cursorPosition);
    }

    function displayErrorsInSidebar() {
        errorList.innerHTML = '';
        const filteredMatches = lastMatches.filter(match => currentFilter === 'All' || match.type === currentFilter);
        if (filteredMatches.length === 0) {
            errorList.innerHTML = `<p class="placeholder-text">${currentFilter === 'All' ? 'No errors detected.' : `No ${currentFilter} errors.`}</p>`;
            return;
        }
        filteredMatches.forEach(match => {
            const card = document.createElement('div');
            card.className = 'error-card';
            card.dataset.offset = match.offset;
            card.dataset.type = match.type;
            card.dataset.ruleId = match.ruleId; // Store ruleId for the link

            const suggestionsHTML = match.replacements.slice(0, 3).map(rep =>
                `<button class="suggestion-btn" data-offset="${match.offset}" data-error-length="${match.errorLength}" data-replacement-text="${escapeHtml(rep)}">${escapeHtml(rep)}</button>`
            ).join('');

            const learnMoreUrl = `https://community.languagetool.org/rule/show/${match.ruleId}?lang=${currentLanguage.split('-')[0]}`;

            card.innerHTML = `
                <div class="error-card-header type-${match.type.toLowerCase()}">
                    <span>${match.type}</span>
                    <a href="${learnMoreUrl}" target="_blank" class="learn-more-link" title="Learn more about this rule">?</a>
                </div>
                <div class="error-card-body">
                    <p>${escapeHtml(match.message)}</p>
                    <div class="suggestions-container">
                        ${suggestionsHTML || 'No suggestions.'}
                    </div>
                </div>`;
            errorList.appendChild(card);
        });
    }

    function populateContextMenu(data) {
        thesaurusResultsEl.innerHTML = data.synonyms.slice(0, 10).map(s => `<span class="synonym">${escapeHtml(s)}</span>`).join('') || 'No synonyms found.';
        dictionaryResultsEl.innerHTML = data.definitions.length > 0 ? `<ul>${data.definitions.slice(0, 3).map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul>` : 'No definition found.';
    }

    function applyCorrection(offset, errorLength, replacementText) {
        const text = editor.innerText;
        const newText = text.substring(0, offset) + replacementText + text.substring(offset + errorLength);
        const oldCursorPos = saveCursorPosition();
        let newCursorPos = oldCursorPos;
        if (oldCursorPos > offset) {
            newCursorPos += replacementText.length - errorLength;
        }
        editor.innerText = newText;
        restoreCursorPosition(newCursorPos);
        handleInput();
    }

    // --- Event Listeners ---
    languageSwitch.addEventListener('click', (event) => {
        const target = event.target.closest('.lang-btn');
        if (target) {
            languageSwitch.querySelector('.active').classList.remove('active');
            target.classList.add('active');
            currentLanguage = target.dataset.lang;
            checkGrammar(editor.innerText);
        }
    });

    fontSelect.addEventListener('change', (event) => {
        editor.style.fontFamily = event.target.value;
    });

    filterControls.addEventListener('click', (event) => {
        const target = event.target.closest('.filter-btn');
        if (target) {
            filterControls.querySelector('.active').classList.remove('active');
            target.classList.add('active');
            currentFilter = target.dataset.filter;
            displayErrorsInSidebar();
        }
    });

    errorList.addEventListener('click', (event) => {
        const suggestionBtn = event.target.closest('.suggestion-btn');
        const card = event.target.closest('.error-card');
        if (suggestionBtn) {
            const { offset, errorLength, replacementText } = suggestionBtn.dataset;
            applyCorrection(parseInt(offset), parseInt(errorLength), replacementText);
        } else if (card) {
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

    editor.addEventListener('contextmenu', (event) => {
        event.preventDefault();
        const selection = window.getSelection();
        let word = selection.toString().trim();
        if (word.length > 0) {
            fetchWordTools(word);
            contextMenu.style.top = `${event.clientY}px`;
            contextMenu.style.left = `${event.clientX}px`;
            contextMenu.classList.remove('hidden');
        }
    });

    window.addEventListener('click', () => {
        contextMenu.classList.add('hidden');
    });

    // --- Cursor Position Handling ---
    function saveCursorPosition() {
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            const preCaretRange = range.cloneRange();
            preCaretRange.selectNodeContents(editor);
            preCaretRange.setEnd(range.endContainer, range.endOffset);
            return preCaretRange.toString().length;
        }
        return 0;
    }

    function restoreCursorPosition(position) {
        let charCount = 0;
        const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while (node = walker.nextNode()) {
            const nodeLength = node.textContent.length;
            if (charCount + nodeLength >= position) {
                const range = document.createRange();
                const sel = window.getSelection();
                try {
                    range.setStart(node, Math.min(position - charCount, nodeLength));
                    range.collapse(true);
                    sel.removeAllRanges();
                    sel.addRange(range);
                } catch (e) { console.error("Error setting cursor position:", e); }
                return;
            }
            charCount += nodeLength;
        }
    }

    // --- Initial State ---
    resetUI();
    editor.focus();
});
