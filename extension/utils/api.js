import {
    readSession,
    assertCurrent,
    establishSession,
    endSession,
} from "./session.js";

export class OwlculusAPI {
    constructor(snapshot = null) {
        this.snapshot = snapshot;
    }

    async request(endpoint, options = {}) {
        const snapshot = this.snapshot
            ? await assertCurrent(this.snapshot)
            : await readSession();
        return this.#requestWithSession(snapshot, endpoint, options);
    }

    async #requestWithSession(snapshot, endpoint, options = {}) {
        const url = new URL(`${snapshot.endpoint}${endpoint}`);
        if (
            !endpoint.startsWith("/api/") ||
            !url.href.startsWith(`${snapshot.endpoint}/api/`)
        ) {
            throw new Error("Invalid API request path");
        }
        const headers = new Headers(options.headers);
        headers.delete("Authorization");
        if (!options.skipAuth) {
            if (!snapshot.session?.token)
                throw new Error("Please sign in to this instance.");
            headers.set(
                "Authorization",
                `${snapshot.session.tokenType} ${snapshot.session.token}`,
            );
        }
        try {
            const response = await fetch(url, {
                ...options,
                headers,
                redirect: "error",
            });

            if (!response.ok) {
                let error;
                const responseText = await response.text();

                try {
                    error = JSON.parse(responseText);
                } catch {
                    error = {
                        detail:
                            responseText ||
                            `HTTP ${response.status}: ${response.statusText}`,
                    };
                }

                if (error.detail && Array.isArray(error.detail)) {
                    const errorMessages = error.detail
                        .map((e) => `${e.loc?.join(".")} - ${e.msg}`)
                        .join(", ");
                    throw new Error(`Validation errors: ${errorMessages}`);
                }

                throw new Error(
                    error.detail ||
                        `HTTP ${response.status}: ${response.statusText}`,
                );
            }

            const result = await response.json();
            await assertCurrent(snapshot);
            return result;
        } catch (error) {
            console.error("API request failed:", error);
            throw error;
        }
    }

    async login(username, password) {
        const formData = new FormData();
        formData.append("username", username);
        formData.append("password", password);

        const snapshot = this.snapshot
            ? await assertCurrent(this.snapshot)
            : await readSession();
        const response = await this.#requestWithSession(
            snapshot,
            "/api/auth/login",
            {
                method: "POST",
                body: formData,
                skipAuth: true,
            },
        );

        if (response.access_token) {
            this.snapshot = await establishSession(snapshot, response);
        }

        return response;
    }

    async getCurrentUser() {
        return this.request("/api/users/me");
    }

    async getCases() {
        return this.request("/api/cases/");
    }

    async createFolder(caseId, folderName) {
        return this.request("/api/evidence/folders", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                title: folderName,
                case_id: caseId,
            }),
        });
    }

    async getFolderTree(caseId) {
        return this.request(`/api/evidence/case/${caseId}/folder-tree`);
    }

    async uploadEvidence(
        caseId,
        title,
        htmlContent,
        pageUrl,
        folderPath = null,
        parentFolderId = null,
    ) {
        const formData = new FormData();

        const htmlBlob = new Blob([htmlContent], { type: "text/html" });
        const filename = `${title.replace(/[^a-z0-9]/gi, "_").toLowerCase()}_${Date.now()}.html`;

        // Create a File object from the Blob (Files are Blobs with additional properties)
        const file = new File([htmlBlob], filename, { type: "text/html" });

        formData.append("files", file);

        // Only append description if it exists (matching web app behavior)
        const description = `Captured from: ${pageUrl}`;
        if (description) {
            formData.append("description", description);
        }

        // Add folder information if provided
        if (folderPath) {
            formData.append("folder_path", folderPath);
        }
        if (parentFolderId) {
            formData.append("parent_folder_id", parentFolderId);
        }

        const queryParams = new URLSearchParams({
            title: title,
            case_id: caseId, // URLSearchParams will convert to string automatically
            category: "Documents", // Default category for web captures
        });

        return this.request(`/api/evidence/?${queryParams}`, {
            method: "POST",
            body: formData,
        });
    }

    async uploadScreenshot(
        caseId,
        title,
        imageBlob,
        pageUrl,
        folderPath = null,
        parentFolderId = null,
    ) {
        const formData = new FormData();

        const filename = `${title.replace(/[^a-z0-9]/gi, "_").toLowerCase()}_${Date.now()}.png`;
        const file = new File([imageBlob], filename, { type: "image/png" });

        formData.append("files", file);

        const description = `Screenshot captured from: ${pageUrl}`;
        if (description) {
            formData.append("description", description);
        }

        // Add folder information if provided
        if (folderPath) {
            formData.append("folder_path", folderPath);
        }
        if (parentFolderId) {
            formData.append("parent_folder_id", parentFolderId);
        }

        const queryParams = new URLSearchParams({
            title: title,
            case_id: caseId,
            category: "Documents", // Default category for screenshots
        });

        return this.request(`/api/evidence/?${queryParams}`, {
            method: "POST",
            body: formData,
        });
    }

    async logout() {
        await endSession();
        this.snapshot = null;
    }
}
