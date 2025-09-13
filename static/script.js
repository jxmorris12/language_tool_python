document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const editor = document.getElementById('editor');
    const errorList = document.getElementById('error-list');
    const wordCountEl = document.getElementById('word-count');
    const languageSwitch = document.getElementById('language-switch');
    const fontSelect = document.getElementById('font-select');
    const contextMenu = document.getElementById('context-menu');
    const thesaurusResultsEl = document.getElementById('thesaurus-results');
    const dictionaryResultsEl = document.getElementById('dictionary-results');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModalOverlay = document.getElementById('settings-modal-overlay');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const categoryToggles = document.getElementById('category-toggles');

    // --- State Variables ---
    let debounceTimer;
    let lastMatches = [];
    let currentLanguage = 'en-US';
    const disabledRules = new Set();
    const disabledCategories = new Set();
    const availableCategories = ['Spelling', 'Grammar', 'Style', 'Typography', 'Clarity', 'Redundancy', 'Misc'];

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
            if (currentText.trim().length > 0) {
                checkGrammar(currentText);
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
        wordCountEl.textContent = 'Words: 0';
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
                body: JSON.stringify({
                    text: text,
                    language: currentLanguage,
                    disabled_rules: Array.from(disabledRules),
                    disabled_categories: Array.from(disabledCategories)
                }),
            });
            if (!response.ok) {
                const errorData = await response.json();
                errorList.innerHTML = `<p class="placeholder-text error-message">API Error: ${errorData.error}</p>`;
                return;
            }
            const matches = await response.json();
            lastMatches = matches || [];
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
    function applyHighlights(matches, text) {
        displayErrorsInSidebar(matches);
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

    function displayErrorsInSidebar(matches) {
        errorList.innerHTML = '';
        if (!matches || matches.length === 0) {
            errorList.innerHTML = '<p class="placeholder-text">No errors detected. Good job!</p>';
            return;
        }
        matches.forEach(match => {
            const card = document.createElement('div');
            card.className = 'error-card';
            card.dataset.offset = match.offset;
            card.dataset.ruleId = match.ruleId;
            const category = match.category; // Using raw category for potential disabling
            const learnMoreUrl = `https://community.languagetool.org/rule/show/${match.ruleId}?lang=${currentLanguage.split('-')[0]}`;

            card.innerHTML = `
                <div class="error-card-header">
                    <span>${escapeHtml(category)}</span>
                    <div class="card-controls">
                        <a href="${learnMoreUrl}" target="_blank" class="learn-more-link" title="Learn more about this rule">?</a>
                        <button class="ignore-rule-btn" title="Ignore this rule">&times;</button>
                    </div>
                </div>
                <div class="error-card-body">
                    <p>${escapeHtml(match.message)}</p>
                    <div class="rule-id-container">Rule: <code>${match.ruleId}</code></div>
                </div>`;
            errorList.appendChild(card);
        });
    }

    function populateContextMenu(data) {
        thesaurusResultsEl.innerHTML = data.synonyms.slice(0, 10).map(s => `<span class="synonym">${escapeHtml(s)}</span>`).join('') || 'No synonyms found.';
        dictionaryResultsEl.innerHTML = data.definitions.length > 0 ? `<ul>${data.definitions.slice(0, 3).map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul>` : 'No definition found.';
    }

    // --- Event Listeners ---
    settingsBtn.addEventListener('click', () => settingsModalOverlay.classList.remove('hidden'));
    closeSettingsBtn.addEventListener('click', () => settingsModalOverlay.classList.add('hidden'));
    settingsModalOverlay.addEventListener('click', (event) => {
        if (event.target === settingsModalOverlay) {
            settingsModalOverlay.classList.add('hidden');
        }
    });

    categoryToggles.addEventListener('change', (event) => {
        const checkbox = event.target;
        const category = checkbox.dataset.category;
        if (checkbox.checked) {
            disabledCategories.delete(category);
        } else {
            disabledCategories.add(category);
        }
        checkGrammar(editor.innerText);
    });

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

    errorList.addEventListener('click', (event) => {
        const ignoreBtn = event.target.closest('.ignore-rule-btn');
        const card = event.target.closest('.error-card');

        if (ignoreBtn) {
            const ruleId = card.dataset.ruleId;
            if (ruleId) {
                disabledRules.add(ruleId);
                checkGrammar(editor.innerText);
            }
        } else if (card) {
            const offset = card.dataset.offset;
            const errorSpan = editor.querySelector(`.grammar-error[data-offset="${offset}"]`);
            if (errorSpan) {
                errorSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });

    editor.addEventListener('contextmenu', (event) => {
        event.preventDefault();
        hideContextMenu();
        const selection = window.getSelection();
        let word = selection.toString().trim();
        if (word.length > 0) {
            fetchWordTools(word);
            contextMenu.style.top = `${event.clientY}px`;
            contextMenu.style.left = `${event.clientX}px`;
            contextMenu.classList.remove('hidden');
        }
    });

    function hideContextMenu() {
        contextMenu.classList.add('hidden');
    }
    window.addEventListener('click', hideContextMenu);
    editor.addEventListener('scroll', hideContextMenu);


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
    function initialize() {
        categoryToggles.innerHTML = availableCategories.map(cat => `
            <div class="category-toggle">
                <input type="checkbox" id="toggle-${cat}" data-category="${cat.toUpperCase()}" checked>
                <label for="toggle-${cat}">${cat}</label>
            </div>
        `).join('');
        resetUI();
        editor.focus();
    }

    initialize();
});
