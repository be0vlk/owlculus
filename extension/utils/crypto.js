export class CryptoHelper {
    constructor() {
        this.algorithm = {name: 'AES-GCM', length: 256};
        this.keyUsages = ['encrypt', 'decrypt'];
    }

    async generateKey() {
        return await crypto.subtle.generateKey(
            this.algorithm,
            true,
            this.keyUsages
        );
    }

    async exportKey(key) {
        const exported = await crypto.subtle.exportKey('jwk', key);
        return JSON.stringify(exported);
    }

    async importKey(keyString) {
        const keyData = JSON.parse(keyString);
        return await crypto.subtle.importKey(
            'jwk',
            keyData,
            this.algorithm,
            true,
            this.keyUsages
        );
    }

    async encrypt(text, key) {
        const encoder = new TextEncoder();
        const data = encoder.encode(text);

        const iv = crypto.getRandomValues(new Uint8Array(12));

        const encrypted = await crypto.subtle.encrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            key,
            data
        );

        const combined = new Uint8Array(iv.byteLength + encrypted.byteLength);
        combined.set(iv, 0);
        combined.set(new Uint8Array(encrypted), iv.byteLength);

        return btoa(String.fromCharCode(...combined));
    }

    async decrypt(encryptedBase64, key) {
        const combined = new Uint8Array(
            atob(encryptedBase64).split('').map(char => char.charCodeAt(0))
        );

        const iv = combined.slice(0, 12);
        const encrypted = combined.slice(12);

        const decrypted = await crypto.subtle.decrypt(
            {
                name: 'AES-GCM',
                iv: iv
            },
            key,
            encrypted
        );

        const decoder = new TextDecoder();
        return decoder.decode(decrypted);
    }

    async deriveKeyFromPassword(password, salt) {
        const encoder = new TextEncoder();
        const keyMaterial = await crypto.subtle.importKey(
            'raw',
            encoder.encode(password),
            {name: 'PBKDF2'},
            false,
            ['deriveBits', 'deriveKey']
        );

        return await crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: encoder.encode(salt),
                iterations: 100000,
                hash: 'SHA-256'
            },
            keyMaterial,
            this.algorithm,
            true,
            this.keyUsages
        );
    }
}

export const cryptoHelper = new CryptoHelper();