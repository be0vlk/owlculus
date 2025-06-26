export const storage = {
  async get(keys) {
    return new Promise((resolve) => {
      chrome.storage.local.get(keys, (result) => {
        resolve(result);
      });
    });
  },

  async set(items) {
    return new Promise((resolve) => {
      chrome.storage.local.set(items, () => {
        resolve();
      });
    });
  },

  async remove(keys) {
    return new Promise((resolve) => {
      chrome.storage.local.remove(keys, () => {
        resolve();
      });
    });
  },

  async clear() {
    return new Promise((resolve) => {
      chrome.storage.local.clear(() => {
        resolve();
      });
    });
  }
};

export const CONFIG_KEYS = {
  API_ENDPOINT: 'apiEndpoint',
  AUTH_TOKEN: 'authToken',
  TOKEN_TYPE: 'tokenType',
  LAST_CASE_ID: 'lastCaseId',
  USER_DATA: 'userData'
};