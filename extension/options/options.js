import { OwlculusAPI } from "../utils/api.js";
import {
    readSession,
    selectEndpoint,
    updateSession,
    assertCurrent,
    watchSession,
    endSession,
} from "../utils/session.js";

let settingsGeneration = 0;

document.addEventListener("DOMContentLoaded", async () => {
    await loadSettings();
    setupEventListeners();
});

async function loadSettings() {
    const started = ++settingsGeneration;
    const snapshot = await readSession();
    if (started !== settingsGeneration) return;
    document.getElementById("api-endpoint").value = snapshot.endpoint;
    if (snapshot.session?.token && snapshot.session.user) {
        showAuthStatus(snapshot.session.user);
    } else {
        showLoginForm();
    }
}

watchSession(() => {
    showLoginForm();
    void loadSettings();
});

function setupEventListeners() {
    document
        .getElementById("api-endpoint")
        .addEventListener("blur", async (e) => {
            try {
                await selectEndpoint(e.target.value);
                await loadSettings();
                showMessage(
                    "API endpoint saved and permission granted!",
                    "success",
                );
            } catch (error) {
                await loadSettings();
                showMessage(error.message, "error");
            }
        });

    document.getElementById("login-btn").addEventListener("click", handleLogin);
    document
        .getElementById("logout-btn")
        .addEventListener("click", handleLogout);

    document.getElementById("password").addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            handleLogin();
        }
    });
}

async function handleLogin() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const loginBtn = document.getElementById("login-btn");

    if (!username || !password) {
        showMessage("Please enter username and password", "error");
        return;
    }

    const endpoint = document.getElementById("api-endpoint").value.trim();
    if (!endpoint) {
        showMessage("Please configure API endpoint first", "error");
        return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "Logging in...";

    try {
        const api = new OwlculusAPI(await selectEndpoint(endpoint));

        const response = await api.login(username, password);

        if (response.access_token) {
            const loginGeneration = settingsGeneration;
            const user = await api.getCurrentUser();
            const userData = {
                username: user.username,
                role: user.role,
            };

            await updateSession(api.snapshot, { user: userData });
            await assertCurrent(api.snapshot);

            if (loginGeneration !== settingsGeneration) return;
            showAuthStatus(userData);
            showMessage("Login successful!", "success");

            document.getElementById("username").value = "";
            document.getElementById("password").value = "";
        }
    } catch (error) {
        console.error("Login error:", error);
        showMessage(error.message || "Login failed", "error");
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = "Login";
    }
}

async function handleLogout() {
    try {
        await endSession();
        showLoginForm();
        showMessage("Logged out successfully", "info");
    } catch (error) {
        console.error("Logout error:", error);
        showMessage("Logout failed", "error");
    }
}

function showLoginForm() {
    document.getElementById("current-user").textContent = "";
    document.getElementById("user-role").textContent = "";
    document.getElementById("login-form").classList.remove("hidden");
    document.getElementById("auth-status").classList.add("hidden");
}

function showAuthStatus(userData) {
    document.getElementById("login-form").classList.add("hidden");
    document.getElementById("auth-status").classList.remove("hidden");
    document.getElementById("current-user").textContent = userData.username;
    document.getElementById("user-role").textContent = userData.role;
}

function showMessage(text, type) {
    const messageDiv = document.getElementById("message");
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    messageDiv.classList.remove("hidden");

    setTimeout(() => {
        messageDiv.classList.add("hidden");
    }, 5000);
}
