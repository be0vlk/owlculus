import {api} from "../utils/api.js";
import {CONFIG_KEYS, storage} from "../utils/storage.js";

let currentUser = null;
let cases = [];

document.addEventListener("DOMContentLoaded", async () => {
    await initializePopup();
    setupEventListeners();
});

async function initializePopup() {
    try {
        const config = await storage.get([
            CONFIG_KEYS.API_ENDPOINT,
            CONFIG_KEYS.AUTH_TOKEN,
        ]);

        if (!config[CONFIG_KEYS.API_ENDPOINT]) {
            showLoginSection();
            updateStatus("No API endpoint configured");
            return;
        }

        if (!config[CONFIG_KEYS.AUTH_TOKEN]) {
            showLoginSection();
            updateStatus("Not logged in");
            return;
        }

        await api.initialize();

        try {
            currentUser = await api.getCurrentUser();
            const userData = {
                username: currentUser.username,
                role: currentUser.role,
            };
            await storage.set({[CONFIG_KEYS.USER_DATA]: userData});

            showCaptureSection();
            updateStatus(`Connected to ${config[CONFIG_KEYS.API_ENDPOINT]}`);
            document.getElementById("username").textContent = currentUser.username;

            await loadCases();
            await setDefaultTitle();
        } catch (error) {
            console.error("Auth check failed:", error);
            showLoginSection();
            updateStatus("Authentication failed");
            await api.logout();
        }
    } catch (error) {
        console.error("Initialization error:", error);
        showLoginSection();
        updateStatus("Extension error");
    }
}

function setupEventListeners() {
    document.getElementById("open-settings").addEventListener("click", () => {
        chrome.runtime.openOptionsPage();
    });

    document.getElementById("logout").addEventListener("click", async () => {
        await api.logout();
        showLoginSection();
        updateStatus("Logged out");
    });

    document
        .getElementById("capture-btn")
        .addEventListener("click", captureCurrentPage);
    document
        .getElementById("screenshot-btn")
        .addEventListener("click", captureScreenshot);

    document
        .getElementById("case-select")
        .addEventListener("change", async (e) => {
            if (e.target.value) {
                await storage.set({[CONFIG_KEYS.LAST_CASE_ID]: e.target.value});
                await loadFolders(e.target.value);
            } else {
                // Clear folders if no case selected
                const folderSelect = document.getElementById("folder-select");
                folderSelect.innerHTML = '<option value="">Select a case first</option>';
            }
        });
}

function showLoginSection() {
    document.getElementById("login-section").classList.remove("hidden");
    document.getElementById("capture-section").classList.add("hidden");
}

function showCaptureSection() {
    document.getElementById("login-section").classList.add("hidden");
    document.getElementById("capture-section").classList.remove("hidden");
}

function updateStatus(message) {
    document.getElementById("status").textContent = message;
}

async function loadCases() {
    try {
        const caseSelect = document.getElementById("case-select");
        caseSelect.innerHTML = '<option value="">Loading cases...</option>';

        cases = await api.getCases();

        if (cases.length === 0) {
            caseSelect.innerHTML = '<option value="">No cases available</option>';
            return;
        }

        caseSelect.innerHTML = '<option value="">Select a case...</option>';
        cases.forEach((caseItem) => {
            const option = document.createElement("option");
            option.value = caseItem.id;
            option.textContent = `${caseItem.case_number} - ${caseItem.title}`;
            caseSelect.appendChild(option);
        });

        const lastCaseId = (await storage.get(CONFIG_KEYS.LAST_CASE_ID))[
            CONFIG_KEYS.LAST_CASE_ID
            ];
        if (lastCaseId && cases.find((c) => c.id == lastCaseId)) {
            caseSelect.value = lastCaseId;
            await loadFolders(lastCaseId);
        }
    } catch (error) {
        console.error("Failed to load cases:", error);
        document.getElementById("case-select").innerHTML =
            '<option value="">Failed to load cases</option>';
    }
}

async function loadFolders(caseId) {
    try {
        const folderSelect = document.getElementById("folder-select");
        folderSelect.innerHTML = '<option value="">Loading folders...</option>';

        const evidenceItems = await api.getFolderTree(caseId);

        // Filter to only get folders (not files)
        const folders = evidenceItems ? evidenceItems.filter(item => item.is_folder) : [];

        if (folders.length === 0) {
            folderSelect.innerHTML = '<option value="">No folders available (will save to root)</option>';
            return;
        }

        // Build hierarchical structure following the main app's approach
        const itemMap = new Map();
        const rootItems = [];

        // First pass: create all folder items
        folders.forEach(folder => {
            const item = {
                id: folder.id,
                title: folder.title,
                folder_path: folder.folder_path,
                parent_folder_id: folder.parent_folder_id,
                children: []
            };
            itemMap.set(folder.id, item);
        });

        // Second pass: build hierarchy
        itemMap.forEach(item => {
            if (item.parent_folder_id && itemMap.has(item.parent_folder_id)) {
                const parent = itemMap.get(item.parent_folder_id);
                parent.children.push(item);
            } else {
                rootItems.push(item);
            }
        });

        // Sort items: by title
        const sortItems = (items) => {
            return items.sort((a, b) => a.title.localeCompare(b.title)).map(item => ({
                ...item,
                children: item.children ? sortItems(item.children) : item.children
            }));
        };

        const sortedItems = sortItems(rootItems);

        // Build folder options with proper hierarchy
        folderSelect.innerHTML = '<option value="">Select a folder (or save to root)</option>';

        function addFolderOptions(folderList, level = 0, parentPrefix = "") {
            folderList.forEach((folder, index) => {
                const option = document.createElement("option");
                option.value = JSON.stringify({
                    id: folder.id,
                    folder_path: folder.folder_path
                });

                // Build visual hierarchy with proper indentation and tree lines
                const isLast = index === folderList.length - 1;
                let prefix = parentPrefix;

                if (level > 0) {
                    // Add tree structure characters
                    prefix += isLast ? "└─ " : "├─ ";
                }

                option.textContent = `${prefix}📁 ${folder.title}`;
                folderSelect.appendChild(option);

                // Recursively add children with updated parent prefix
                if (folder.children && folder.children.length > 0) {
                    const childPrefix = parentPrefix + (level > 0 ? (isLast ? "   " : "│  ") : "");
                    addFolderOptions(folder.children, level + 1, childPrefix);
                }
            });
        }

        addFolderOptions(sortedItems);
    } catch (error) {
        console.error("Failed to load folders:", error);
        document.getElementById("folder-select").innerHTML =
            '<option value="">Failed to load folders (will save to root)</option>';
    }
}

async function setDefaultTitle() {
    try {
        const [tab] = await chrome.tabs.query({
            active: true,
            currentWindow: true,
        });
        if (tab && tab.title) {
            document.getElementById("title-input").placeholder = tab.title;
        }
    } catch (error) {
        console.error("Failed to get tab title:", error);
    }
}

async function captureCurrentPage() {
    const captureBtn = document.getElementById("capture-btn");
    const btnText = captureBtn.querySelector(".btn-text");
    const spinner = captureBtn.querySelector(".spinner");
    const resultDiv = document.getElementById("result");

    const caseId = parseInt(document.getElementById("case-select").value, 10);
    if (!caseId) {
        showResult("Please select a case", "error");
        return;
    }

    captureBtn.disabled = true;
    btnText.textContent = "Capturing...";
    spinner.classList.remove("hidden");
    resultDiv.classList.add("hidden");

    try {
        const [tab] = await chrome.tabs.query({
            active: true,
            currentWindow: true,
        });

        let captureResult;
        try {
            captureResult = await chrome.tabs.sendMessage(tab.id, {
                action: "captureHTML",
            });
        } catch (error) {
            if (error.message.includes("Could not establish connection")) {
                await chrome.scripting.executeScript({
                    target: {tabId: tab.id},
                    files: ["content/content.js"],
                });

                captureResult = await chrome.tabs.sendMessage(tab.id, {
                    action: "captureHTML",
                });
            } else {
                throw error;
            }
        }

        if (!captureResult.success) {
            throw new Error(captureResult.error || "Failed to capture page");
        }

        btnText.textContent = "Uploading...";

        const title =
            document.getElementById("title-input").value ||
            tab.title ||
            "Captured Page";

        // Get selected folder information
        const folderSelectValue = document.getElementById("folder-select").value;
        let folderPath = null;
        let parentFolderId = null;

        if (folderSelectValue) {
            try {
                const folderInfo = JSON.parse(folderSelectValue);
                folderPath = folderInfo.folder_path;
                parentFolderId = folderInfo.id;
            } catch (e) {
                console.error("Failed to parse folder info:", e);
            }
        }

        const uploadResult = await api.uploadEvidence(
            caseId,
            title,
            captureResult.html,
            tab.url,
            folderPath,
            parentFolderId
        );

        if (uploadResult && uploadResult.length > 0) {
            showResult("Evidence uploaded successfully!", "success");

            setTimeout(() => {
                window.close();
            }, 2000);
        } else {
            throw new Error("Upload returned no results");
        }
    } catch (error) {
        console.error("Capture error:", error);
        showResult(error.message || "Failed to capture page", "error");
    } finally {
        captureBtn.disabled = false;
        btnText.textContent = "Capture Page";
        spinner.classList.add("hidden");
    }
}

async function captureScreenshot() {
    const screenshotBtn = document.getElementById("screenshot-btn");
    const btnText = screenshotBtn.querySelector(".btn-text");
    const spinner = screenshotBtn.querySelector(".spinner");
    const resultDiv = document.getElementById("result");

    const caseId = parseInt(document.getElementById("case-select").value, 10);
    if (!caseId) {
        showResult("Please select a case", "error");
        return;
    }

    screenshotBtn.disabled = true;
    btnText.textContent = "Capturing...";
    spinner.classList.remove("hidden");
    resultDiv.classList.add("hidden");

    try {
        const [tab] = await chrome.tabs.query({
            active: true,
            currentWindow: true,
        });

        const dataUrl = await chrome.tabs.captureVisibleTab(null, {
            format: "png",
            quality: 90,
        });

        btnText.textContent = "Uploading...";

        const title =
            document.getElementById("title-input").value ||
            `Screenshot - ${tab.title || "Unknown Page"}`;

        // Get selected folder information
        const folderSelectValue = document.getElementById("folder-select").value;
        let folderPath = null;
        let parentFolderId = null;

        if (folderSelectValue) {
            try {
                const folderInfo = JSON.parse(folderSelectValue);
                folderPath = folderInfo.folder_path;
                parentFolderId = folderInfo.id;
            } catch (e) {
                console.error("Failed to parse folder info:", e);
            }
        }

        const response = await fetch(dataUrl);
        const blob = await response.blob();

        const uploadResult = await api.uploadScreenshot(
            caseId,
            title,
            blob,
            tab.url,
            folderPath,
            parentFolderId
        );

        if (uploadResult && uploadResult.length > 0) {
            showResult("Screenshot uploaded successfully!", "success");

            setTimeout(() => {
                window.close();
            }, 2000);
        } else {
            throw new Error("Upload returned no results");
        }
    } catch (error) {
        console.error("Screenshot error:", error);
        showResult(error.message || "Failed to capture screenshot", "error");
    } finally {
        screenshotBtn.disabled = false;
        btnText.textContent = "Screenshot";
        spinner.classList.add("hidden");
    }
}

function showResult(message, type) {
    const resultDiv = document.getElementById("result");
    resultDiv.textContent = message;
    resultDiv.className = `result ${type}`;
    resultDiv.classList.remove("hidden");
}
