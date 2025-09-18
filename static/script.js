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
    const errorDetailsOverlay = document.getElementById('error-details-overlay');
    const closeErrorDetailsBtn = document.getElementById('close-error-details-btn');
    const errorMessageEl = document.getElementById('error-details-message');
    const errorSentenceEl = document.getElementById('error-details-sentence');
    const errorReplacementsEl = document.getElementById('error-details-replacements');
    const errorCategoryEl = document.getElementById('error-details-category');
    const errorIssueTypeEl = document.getElementById('error-details-issue-type');
    const errorRuleIdEl = document.getElementById('error-details-rule-id');
    const saveBtn = document.getElementById('save-btn');
    const loadBtn = document.getElementById('load-btn');
    const fileInput = document.getElementById('file-input');
    const projectPane = document.getElementById('project-pane');
    const newFileBtn = document.getElementById('new-file-btn');
    const snapshotsBtn = document.getElementById('snapshots-btn');
    const snapshotsOverlay = document.getElementById('snapshots-overlay');
    const snapshotsList = document.getElementById('snapshots-list');
    const closeSnapshotsBtn = document.getElementById('close-snapshots-btn');
    const snapshotThresholdInput = document.getElementById('snapshot-threshold-input');


    // --- State Variables ---
    let debounceTimer;
    let lastMatches = [];
    let currentLanguage = 'en-US';
    const disabledRules = new Set();
    const disabledCategories = new Set();
    const availableCategories = ['Spelling', 'Grammar', 'Style', 'Typography', 'Clarity', 'Redundancy', 'Misc'];
    let projectState = {
        files: [],
        activeFileId: null,
        snapshotThreshold: 50, // Default to 50 words
    };

    // --- Utility to escape HTML ---
    function escapeHtml(unsafe) {
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // --- Input Handling ---
    const handleInput = () => {
        clearTimeout(debounceTimer);
        const currentText = editor.innerText;

        // Update state before doing anything else
        const activeFile = projectState.files.find(f => f.id === projectState.activeFileId);
        if (activeFile) {
            activeFile.content = currentText;
            saveStateToLocalStorage(); // Autosave on input
        }

        updateWordCount(currentText);
        debounceTimer = setTimeout(() => {
            // Automatic snapshot logic
            if (activeFile) {
                const wordCount = currentText.trim().split(/\s+/).filter(Boolean).length;
                if (wordCount - activeFile.lastSnapshotWordCount >= projectState.snapshotThreshold) {
                    createSnapshot(projectState.activeFileId, `Auto-saved at ${wordCount} words`);
                }
            }
            if (currentText.trim().length > 0) {
                checkGrammar(currentText);
            } else {
                // Clear highlights and errors, but don't reset the editor content
                lastMatches = [];
                errorList.innerHTML = '<p class="placeholder-text">Start typing to see suggestions.</p>';
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
                errorList.innerHTML = `<p class="placeholder-text error-message">${errorData.error}</p>`;
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

    // --- Persistence ---

    function saveStateToLocalStorage() {
        localStorage.setItem('typerfect_project_state', JSON.stringify(projectState));
    }

    function loadStateFromLocalStorage() {
        const savedState = localStorage.getItem('typerfect_project_state');
        if (savedState) {
            projectState = JSON.parse(savedState);
        }
    }


    // --- Project Pane & File Management ---

    function renderProjectPane() {
        projectPane.innerHTML = '';
        projectState.files.forEach(file => {
            const tab = document.createElement('div');
            tab.className = 'file-tab';
            tab.dataset.fileId = file.id;
            if (file.id === projectState.activeFileId) {
                tab.classList.add('active');
            }

            const tabName = document.createElement('span');
            tabName.textContent = file.name;
            tab.appendChild(tabName);

            const closeBtn = document.createElement('button');
            closeBtn.className = 'close-tab-btn';
            closeBtn.innerHTML = '&times;';
            tab.appendChild(closeBtn);

            projectPane.appendChild(tab);
        });
    }

    function setActiveFile(fileId) {
        projectState.activeFileId = fileId;
        const activeFile = projectState.files.find(f => f.id === fileId);

        if (activeFile) {
            editor.innerText = activeFile.content;
        } else {
            editor.innerText = ''; // Or handle error
        }

        handleInput(); // Trigger word count and grammar check
        renderProjectPane();
        saveStateToLocalStorage();
    }

    function addNewFile() {
        const newFile = {
            id: Date.now(), // Simple unique ID
            name: `Untitled-${projectState.files.length + 1}`,
            content: '',
            snapshots: [],
            lastSnapshotWordCount: 0,
        };
        projectState.files.push(newFile);
        createSnapshot(newFile.id, "Created"); // Create initial snapshot
        setActiveFile(newFile.id);
    }

    // --- Snapshots ---

    function createSnapshot(fileId, name) {
        const file = projectState.files.find(f => f.id === fileId);
        if (!file) return;

        const wordCount = file.content.trim().split(/\s+/).filter(Boolean).length;
        const snapshot = {
            id: Date.now(),
            name: name,
            date: new Date().toLocaleString(),
            wordCount: wordCount,
            content: file.content,
        };
        file.snapshots.unshift(snapshot); // Add to the beginning of the array
        file.lastSnapshotWordCount = wordCount;
        saveStateToLocalStorage();
    }

    function showSnapshots() {
        const activeFile = projectState.files.find(f => f.id === projectState.activeFileId);
        if (!activeFile || !activeFile.snapshots || activeFile.snapshots.length === 0) {
            snapshotsList.innerHTML = '<p class="placeholder-text">No snapshots for this file yet.</p>';
        } else {
            snapshotsList.innerHTML = activeFile.snapshots.map(snapshot => `
                <div class="snapshot-item" data-snapshot-id="${snapshot.id}">
                    <div class="snapshot-info">
                        <div class="snapshot-name">${escapeHtml(snapshot.name)}</div>
                        <div class="snapshot-date">${snapshot.date} (${snapshot.wordCount} words)</div>
                    </div>
                    <div class="snapshot-actions">
                        <button class="action-btn restore-snapshot-btn">Restore</button>
                    </div>
                </div>
            `).join('');
        }
        snapshotsOverlay.style.display = 'flex';
    }

    function restoreSnapshot(snapshotId) {
        const activeFile = projectState.files.find(f => f.id === projectState.activeFileId);
        if (!activeFile) return;

        const snapshot = activeFile.snapshots.find(s => s.id === snapshotId);
        if (snapshot) {
            activeFile.content = snapshot.content;
            editor.innerText = snapshot.content;
            handleInput();
            saveStateToLocalStorage();
            snapshotsOverlay.style.display = 'none'; // Close modal after restore
        }
    }


    function closeFile(fileIdToClose) {
        const fileIndex = projectState.files.findIndex(f => f.id === fileIdToClose);
        if (fileIndex === -1) return;

        projectState.files.splice(fileIndex, 1);

        if (projectState.activeFileId === fileIdToClose) {
            if (projectState.files.length > 0) {
                // Activate the previous file, or the first one if the closed one was the first
                const newActiveIndex = Math.max(0, fileIndex - 1);
                setActiveFile(projectState.files[newActiveIndex].id);
            } else {
                // If no files are left, create a new one
                addNewFile();
            }
        } else {
            renderProjectPane();
        }
        saveStateToLocalStorage();
    }


    // --- UI Rendering ---
    function removeHighlights() {
        const highlights = editor.querySelectorAll('.grammar-error');
        highlights.forEach(span => {
            const parent = span.parentNode;
            while (span.firstChild) {
                parent.insertBefore(span.firstChild, span);
            }
            parent.removeChild(span);
            parent.normalize(); // Merges adjacent text nodes
        });
    }

    function applyHighlights(matches) {
        const text = editor.innerText;
        // Only render highlights if the text matches the active file's content
        const activeFile = projectState.files.find(f => f.id === projectState.activeFileId);
        if (!activeFile || text !== activeFile.content) {
            return; // Stale check, ignore
        }

        displayErrorsInSidebar(matches);

        const cursorPosition = saveCursorPosition();

        removeHighlights();

        if (!matches || matches.length === 0) {
            restoreCursorPosition(cursorPosition);
            return;
        }

        // Iterate backwards to avoid offset issues
        for (let i = matches.length - 1; i >= 0; i--) {
            const match = matches[i];
            const range = document.createRange();
            let startContainer, startOffset, endContainer, endOffset;
            let charCount = 0;
            const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT, null, false);

            let currentNode;
            while (currentNode = walker.nextNode()) {
                const nodeLength = currentNode.textContent.length;
                if (!startContainer && charCount + nodeLength >= match.offset) {
                    startContainer = currentNode;
                    startOffset = match.offset - charCount;
                }
                if (!endContainer && charCount + nodeLength >= match.offset + match.errorLength) {
                    endContainer = currentNode;
                    endOffset = (match.offset + match.errorLength) - charCount;
                    break;
                }
                charCount += nodeLength;
            }

            if (startContainer && endContainer) {
                range.setStart(startContainer, startOffset);
                range.setEnd(endContainer, endOffset);

                const highlightSpan = document.createElement('span');
                highlightSpan.className = 'grammar-error';
                highlightSpan.dataset.offset = match.offset;

                try {
                    range.surroundContents(highlightSpan);
                } catch (e) {
                    console.error("Could not surround contents for match:", match, e);
                }
            }
        }

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
                        <button class="ignore-rule-btn" title="Ignore this rule">&times;</button>
                    </div>
                </div>
                <div class="error-card-body">
                    <p>${escapeHtml(match.message)}</p>
                </div>
                <div class="error-card-footer">
                    <a href="${learnMoreUrl}" target="_blank" class="learn-more-link">
                        Learn more about: <strong>${escapeHtml(match.ruleId)}</strong>
                    </a>
                </div>`;
            errorList.appendChild(card);
        });
    }

    function populateContextMenu(data) {
        thesaurusResultsEl.innerHTML = data.synonyms.slice(0, 10).map(s => `<span class="synonym">${escapeHtml(s)}</span>`).join('') || 'No synonyms found.';
        dictionaryResultsEl.innerHTML = data.definitions.length > 0 ? `<ul>${data.definitions.slice(0, 3).map(d => `<li>${escapeHtml(d)}</li>`).join('')}</ul>` : 'No definition found.';
    }

    // --- File Handling ---
    function saveTextAsFile() {
        const activeFile = projectState.files.find(f => f.id === projectState.activeFileId);
        if (!activeFile) return;

        const text = activeFile.content;
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'typerfect-document.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function loadFileContent(event) {
        const file = event.target.files[0];
        if (!file) {
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            const newFile = {
                id: Date.now(),
                name: file.name,
                content: content,
                snapshots: [],
                lastSnapshotWordCount: 0,
            };
            projectState.files.push(newFile);
            createSnapshot(newFile.id, "Loaded from file");
            setActiveFile(newFile.id);
        };
        reader.readAsText(file);

        // Reset file input so the same file can be loaded again
        fileInput.value = '';
    }


    function showErrorDetails(match) {
        if (!match) return;

        errorMessageEl.textContent = match.message;
        errorSentenceEl.textContent = match.sentence;
        errorCategoryEl.textContent = match.category;
        errorIssueTypeEl.textContent = match.ruleIssueType;
        errorRuleIdEl.textContent = match.ruleId;
        errorRuleIdEl.href = `https://community.languagetool.org/rule/show/${match.ruleId}?lang=${currentLanguage.split('-')[0]}`;

        if (match.replacements && match.replacements.length > 0) {
            errorReplacementsEl.innerHTML = match.replacements.map(r => `<button class="suggestion-btn">${escapeHtml(r)}</button>`).join('');
        } else {
            errorReplacementsEl.innerHTML = '<p>No replacements available.</p>';
        }

        errorDetailsOverlay.style.display = 'flex';
    }

    // --- Event Listeners ---
    saveBtn.addEventListener('click', saveTextAsFile);
    loadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', loadFileContent);
    newFileBtn.addEventListener('click', addNewFile);
    snapshotsBtn.addEventListener('click', showSnapshots);

    snapshotsList.addEventListener('click', (event) => {
        if (event.target.classList.contains('restore-snapshot-btn')) {
            const snapshotItem = event.target.closest('.snapshot-item');
            const snapshotId = parseInt(snapshotItem.dataset.snapshotId, 10);
            restoreSnapshot(snapshotId);
        }
    });

    const closeSnapshotsModal = () => {
        snapshotsOverlay.style.display = 'none';
    };

    closeSnapshotsBtn.addEventListener('click', closeSnapshotsModal);
    snapshotsOverlay.addEventListener('click', (event) => {
        if (event.target === snapshotsOverlay) {
            closeSnapshotsModal();
        }
    });

    projectPane.addEventListener('click', (event) => {
        const tab = event.target.closest('.file-tab');
        const closeBtn = event.target.closest('.close-tab-btn');

        if (closeBtn) {
            event.stopPropagation();
            const fileIdToClose = parseInt(tab.dataset.fileId, 10);
            closeFile(fileIdToClose);
        } else if (tab) {
            const fileIdToSwitch = parseInt(tab.dataset.fileId, 10);
            setActiveFile(fileIdToSwitch);
        }
    });

    settingsBtn.addEventListener('click', () => {
        settingsModalOverlay.style.display = 'flex';
    });

    const closeSettingsModal = () => {
        settingsModalOverlay.style.display = 'none';
    };

    closeSettingsBtn.addEventListener('click', closeSettingsModal);
    settingsModalOverlay.addEventListener('click', (event) => {
        if (event.target === settingsModalOverlay) {
            closeSettingsModal();
        }
    });

    const closeErrorDetailsModal = () => {
        errorDetailsOverlay.style.display = 'none';
    };

    closeErrorDetailsBtn.addEventListener('click', closeErrorDetailsModal);
    errorDetailsOverlay.addEventListener('click', (event) => {
        if (event.target === errorDetailsOverlay) {
            closeErrorDetailsModal();
        }
    });

    snapshotThresholdInput.addEventListener('change', () => {
        const newThreshold = parseInt(snapshotThresholdInput.value, 10);
        if (!isNaN(newThreshold) && newThreshold >= 10) {
            projectState.snapshotThreshold = newThreshold;
            saveStateToLocalStorage();
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
        const learnMoreLink = event.target.closest('.learn-more-link');
        const card = event.target.closest('.error-card');

        if (ignoreBtn) {
            event.stopPropagation(); // Prevent card click from firing
            const ruleId = card.dataset.ruleId;
            if (ruleId) {
                disabledRules.add(ruleId);
                checkGrammar(editor.innerText);
            }
        } else if (learnMoreLink) {
            event.stopPropagation(); // Prevent card click from firing
            // Link will open in new tab automatically
        } else if (card) {
            const offset = parseInt(card.dataset.offset, 10);
            const match = lastMatches.find(m => m.offset === offset);
            showErrorDetails(match);
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
        // Hide modals by default
        settingsModalOverlay.style.display = 'none';
        errorDetailsOverlay.style.display = 'none';
        snapshotsOverlay.style.display = 'none';

        categoryToggles.innerHTML = availableCategories.map(cat => `
            <div class="category-toggle">
                <input type="checkbox" id="toggle-${cat}" data-category="${cat.toUpperCase()}" checked>
                <label for="toggle-${cat}">${cat}</label>
            </div>
        `).join('');

        // Initialize project state
        loadStateFromLocalStorage();

        // Set initial value for settings
        snapshotThresholdInput.value = projectState.snapshotThreshold || 50;

        if (projectState.files.length === 0) {
            addNewFile(); // Start with one untitled file if storage is empty
        } else {
            // Ensure loaded files have snapshot properties for backward compatibility
            projectState.files.forEach(file => {
                if (!file.snapshots) {
                    file.snapshots = [];
                    file.lastSnapshotWordCount = 0;
                    createSnapshot(file.id, "Initial version");
                }
            });
            setActiveFile(projectState.activeFileId);
        }

        editor.focus();
    }

    initialize();
});
