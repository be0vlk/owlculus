import { CONFIG_KEYS, storage } from "./storage.js";

export function normalizeEndpoint(value) {
    const url = new URL(value.trim());
    if (
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password ||
        url.search ||
        url.hash
    ) {
        throw new Error(
            "Use an HTTP(S) endpoint without credentials, query, or fragment",
        );
    }
    return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
}

// Web Locks serialize session mutations across popup and options contexts.
const locked = (callback) =>
    navigator.locks.request("owlculus-session", callback);

export async function readSession() {
    const config = await storage.get([
        CONFIG_KEYS.API_ENDPOINT,
        CONFIG_KEYS.SESSION,
        CONFIG_KEYS.SESSION_REVISION,
    ]);
    const endpoint = normalizeEndpoint(
        config[CONFIG_KEYS.API_ENDPOINT] || "http://localhost",
    );
    const saved = config[CONFIG_KEYS.SESSION];
    return {
        endpoint,
        revision: config[CONFIG_KEYS.SESSION_REVISION] || null,
        session: saved?.endpoint === endpoint ? saved : null,
    };
}

export async function assertCurrent(snapshot) {
    const current = await readSession();
    if (
        current.endpoint !== snapshot.endpoint ||
        current.revision !== snapshot.revision
    ) {
        throw new Error("Instance or session changed. Please sign in again.");
    }
    return current;
}

async function clearLegacy() {
    await storage.remove([
        CONFIG_KEYS.AUTH_TOKEN,
        CONFIG_KEYS.TOKEN_TYPE,
        CONFIG_KEYS.USER_DATA,
        CONFIG_KEYS.LAST_CASE_ID,
    ]);
}

export async function selectEndpoint(value) {
    const endpoint = normalizeEndpoint(value);
    // Permission must be requested directly from the user gesture, before awaiting storage.
    const granted = await chrome.permissions.request({
        origins: [`${new URL(endpoint).origin}/*`],
    });
    if (!granted)
        throw new Error(
            "Permission was not granted. Previous instance retained.",
        );
    return locked(async () => {
        const current = await readSession();
        if (current.endpoint !== endpoint) {
            await storage.set({
                [CONFIG_KEYS.API_ENDPOINT]: endpoint,
                [CONFIG_KEYS.SESSION]: null,
                [CONFIG_KEYS.SESSION_REVISION]: crypto.randomUUID(),
            });
            await clearLegacy();
        }
        return readSession();
    });
}

export async function establishSession(snapshot, response) {
    return locked(async () => {
        await assertCurrent(snapshot);
        await storage.set({
            [CONFIG_KEYS.SESSION]: {
                endpoint: snapshot.endpoint,
                token: response.access_token,
                tokenType: response.token_type || "bearer",
            },
            [CONFIG_KEYS.SESSION_REVISION]: crypto.randomUUID(),
        });
        await clearLegacy();
        return readSession();
    });
}

export async function updateSession(snapshot, values) {
    return locked(async () => {
        const current = await assertCurrent(snapshot);
        if (!current.session)
            throw new Error("Please sign in to this instance.");
        await storage.set({
            [CONFIG_KEYS.SESSION]: { ...current.session, ...values },
        });
    });
}

export async function endSession() {
    return locked(async () => {
        await storage.set({
            [CONFIG_KEYS.SESSION]: null,
            [CONFIG_KEYS.SESSION_REVISION]: crypto.randomUUID(),
        });
        await clearLegacy();
    });
}

export function watchSession(callback) {
    storage.watch(
        [CONFIG_KEYS.API_ENDPOINT, CONFIG_KEYS.SESSION_REVISION],
        callback,
    );
}
