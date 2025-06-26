import { api } from '../utils/api.js';
import { storage, CONFIG_KEYS } from '../utils/storage.js';

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  setupEventListeners();
});

async function loadSettings() {
  const config = await storage.get([
    CONFIG_KEYS.API_ENDPOINT,
    CONFIG_KEYS.AUTH_TOKEN,
    CONFIG_KEYS.USER_DATA
  ]);
  
  if (config[CONFIG_KEYS.API_ENDPOINT]) {
    document.getElementById('api-endpoint').value = config[CONFIG_KEYS.API_ENDPOINT];
  }
  
  if (config[CONFIG_KEYS.AUTH_TOKEN] && config[CONFIG_KEYS.USER_DATA]) {
    showAuthStatus(config[CONFIG_KEYS.USER_DATA]);
  } else {
    showLoginForm();
  }
}

function setupEventListeners() {
  document.getElementById('api-endpoint').addEventListener('blur', async (e) => {
    const endpoint = e.target.value.trim();
    if (endpoint) {
      if (!endpoint.startsWith('http://') && !endpoint.startsWith('https://')) {
        showMessage('API endpoint must start with http:// or https://', 'error');
        return;
      }
      
      await storage.set({ [CONFIG_KEYS.API_ENDPOINT]: endpoint });
      showMessage('API endpoint saved', 'success');
      
      const hasToken = (await storage.get(CONFIG_KEYS.AUTH_TOKEN))[CONFIG_KEYS.AUTH_TOKEN];
      if (!hasToken) {
        showLoginForm();
      }
    }
  });
  
  document.getElementById('login-btn').addEventListener('click', handleLogin);
  document.getElementById('logout-btn').addEventListener('click', handleLogout);
  
  document.getElementById('password').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      handleLogin();
    }
  });
}

async function handleLogin() {
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const loginBtn = document.getElementById('login-btn');
  
  if (!username || !password) {
    showMessage('Please enter username and password', 'error');
    return;
  }
  
  const endpoint = document.getElementById('api-endpoint').value.trim();
  if (!endpoint) {
    showMessage('Please configure API endpoint first', 'error');
    return;
  }
  
  loginBtn.disabled = true;
  loginBtn.textContent = 'Logging in...';
  
  try {
    await storage.set({ [CONFIG_KEYS.API_ENDPOINT]: endpoint });
    await api.initialize();
    
    const response = await api.login(username, password);
    
    if (response.access_token) {
      const user = await api.getCurrentUser();
      const userData = {
        username: user.username,
        role: user.role
      };
      
      await storage.set({ [CONFIG_KEYS.USER_DATA]: userData });
      
      showAuthStatus(userData);
      showMessage('Login successful!', 'success');
      
      document.getElementById('username').value = '';
      document.getElementById('password').value = '';
    }
  } catch (error) {
    console.error('Login error:', error);
    showMessage(error.message || 'Login failed', 'error');
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'Login';
  }
}

async function handleLogout() {
  try {
    await api.logout();
    showLoginForm();
    showMessage('Logged out successfully', 'info');
  } catch (error) {
    console.error('Logout error:', error);
    showMessage('Logout failed', 'error');
  }
}

function showLoginForm() {
  document.getElementById('login-form').classList.remove('hidden');
  document.getElementById('auth-status').classList.add('hidden');
}

function showAuthStatus(userData) {
  document.getElementById('login-form').classList.add('hidden');
  document.getElementById('auth-status').classList.remove('hidden');
  document.getElementById('current-user').textContent = userData.username;
  document.getElementById('user-role').textContent = userData.role;
}

function showMessage(text, type) {
  const messageDiv = document.getElementById('message');
  messageDiv.textContent = text;
  messageDiv.className = `message ${type}`;
  messageDiv.classList.remove('hidden');
  
  setTimeout(() => {
    messageDiv.classList.add('hidden');
  }, 5000);
}