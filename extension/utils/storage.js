import {cryptoHelper} from './crypto.js';

const ENCRYPTION_KEY_NAME = '_owlculus_encryption_key';
const ENCRYPTED_PREFIX = 'enc_';

class EncryptedStorage {
    constructor() {
        this.encryptionKey = null;
    }

    async ensureEncryptionKey() {
        if (this.encryptionKey) {
            return this.encryptionKey;
        }

        return new Promise((resolve) => {
            chrome.storage.local.get([ENCRYPTION_KEY_NAME], async (result) => {
                if (result[ENCRYPTION_KEY_NAME]) {
                    this.encryptionKey = await cryptoHelper.importKey(result[ENCRYPTION_KEY_NAME]);
                } else {
                    this.encryptionKey = await cryptoHelper.generateKey();
                    const exportedKey = await cryptoHelper.exportKey(this.encryptionKey);
                    chrome.storage.local.set({[ENCRYPTION_KEY_NAME]: exportedKey});
                }
                resolve(this.encryptionKey);
            });
        });
    }

    async get(keys) {
        const key = await this.ensureEncryptionKey();

        return new Promise((resolve) => {
            const encryptedKeys = Array.isArray(keys)
                ? keys.map(k => ENCRYPTED_PREFIX + k)
                : [ENCRYPTED_PREFIX + keys];

            chrome.storage.local.get(encryptedKeys, async (result) => {
                const decryptedResult = {};

                for (const [encKey, encValue] of Object.entries(result)) {
                    if (encValue) {
                        const originalKey = encKey.substring(ENCRYPTED_PREFIX.length);
                        try {
                            decryptedResult[originalKey] = JSON.parse(
                                await cryptoHelper.decrypt(encValue, key)
                            );
                        } catch (e) {
                            console.error('Failed to decrypt value for', originalKey, e);
                        }
                    }
                }

                resolve(decryptedResult);
            });
        });
    }

    async set(items) {
        const key = await this.ensureEncryptionKey();
        const encryptedItems = {};

        for (const [itemKey, value] of Object.entries(items)) {
            try {
                const encrypted = await cryptoHelper.encrypt(JSON.stringify(value), key);
                encryptedItems[ENCRYPTED_PREFIX + itemKey] = encrypted;
            } catch (e) {
                console.error('Failed to encrypt value for', itemKey, e);
            }
        }

        return new Promise((resolve) => {
            chrome.storage.local.set(encryptedItems, () => {
                resolve();
            });
        });
    }

    async remove(keys) {
        const encryptedKeys = Array.isArray(keys)
            ? keys.map(k => ENCRYPTED_PREFIX + k)
            : [ENCRYPTED_PREFIX + keys];

        return new Promise((resolve) => {
            chrome.storage.local.remove(encryptedKeys, () => {
                resolve();
            });
        });
    }

    async clear() {
        return new Promise((resolve) => {
            chrome.storage.local.get(null, (allItems) => {
                const keysToRemove = Object.keys(allItems).filter(
                    key => key.startsWith(ENCRYPTED_PREFIX)
                );
                chrome.storage.local.remove(keysToRemove, () => {
                    resolve();
                });
            });
        });
    }
}

export const storage = new EncryptedStorage();

export const CONFIG_KEYS = {
    API_ENDPOINT: "apiEndpoint",
    AUTH_TOKEN: "authToken",
    TOKEN_TYPE: "tokenType",
    LAST_CASE_ID: "lastCaseId",
    USER_DATA: "userData",
};
