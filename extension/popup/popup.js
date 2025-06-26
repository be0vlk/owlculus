import { api } from '../utils/api.js';
import { storage, CONFIG_KEYS } from '../utils/storage.js';

let currentUser = null;
let cases = [];

document.addEventListener('DOMContentLoaded', async () => {
  await initializePopup();
  setupEventListeners();
});

async function initializePopup() {
  try {
    const config = await storage.get([CONFIG_KEYS.API_ENDPOINT, CONFIG_KEYS.AUTH_TOKEN]);
    
    if (!config[CONFIG_KEYS.API_ENDPOINT]) {
      showLoginSection();
      updateStatus('No API endpoint configured');
      return;
    }

    if (!config[CONFIG_KEYS.AUTH_TOKEN]) {
      showLoginSection();
      updateStatus('Not logged in');
      return;
    }

    await api.initialize();
    
    try {
      currentUser = await api.getCurrentUser();
      const userData = {
        username: currentUser.username,
        role: currentUser.role
      };
      await storage.set({ [CONFIG_KEYS.USER_DATA]: userData });
      
      showCaptureSection();
      updateStatus(`Connected to ${config[CONFIG_KEYS.API_ENDPOINT]}`);
      document.getElementById('username').textContent = currentUser.username;
      
      await loadCases();
      await setDefaultTitle();
      
    } catch (error) {
      console.error('Auth check failed:', error);
      showLoginSection();
      updateStatus('Authentication failed');
      await api.logout();
    }
  } catch (error) {
    console.error('Initialization error:', error);
    showLoginSection();
    updateStatus('Extension error');
  }
}

function setupEventListeners() {
  document.getElementById('open-settings').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });

  document.getElementById('logout').addEventListener('click', async () => {
    await api.logout();
    showLoginSection();
    updateStatus('Logged out');
  });

  document.getElementById('capture-btn').addEventListener('click', captureCurrentPage);
  document.getElementById('screenshot-btn').addEventListener('click', captureScreenshot);

  document.getElementById('case-select').addEventListener('change', async (e) => {
    if (e.target.value) {
      await storage.set({ [CONFIG_KEYS.LAST_CASE_ID]: e.target.value });
    }
  });
}

function showLoginSection() {
  document.getElementById('login-section').classList.remove('hidden');
  document.getElementById('capture-section').classList.add('hidden');
}

function showCaptureSection() {
  document.getElementById('login-section').classList.add('hidden');
  document.getElementById('capture-section').classList.remove('hidden');
}

function updateStatus(message) {
  document.getElementById('status').textContent = message;
}

async function loadCases() {
  try {
    const caseSelect = document.getElementById('case-select');
    caseSelect.innerHTML = '<option value="">Loading cases...</option>';
    
    cases = await api.getCases();
    
    if (cases.length === 0) {
      caseSelect.innerHTML = '<option value="">No cases available</option>';
      return;
    }
    
    caseSelect.innerHTML = '<option value="">Select a case...</option>';
    cases.forEach(caseItem => {
      const option = document.createElement('option');
      option.value = caseItem.id;
      option.textContent = `${caseItem.case_number} - ${caseItem.title}`;
      caseSelect.appendChild(option);
    });
    
    const lastCaseId = (await storage.get(CONFIG_KEYS.LAST_CASE_ID))[CONFIG_KEYS.LAST_CASE_ID];
    if (lastCaseId && cases.find(c => c.id == lastCaseId)) {
      caseSelect.value = lastCaseId;
    }
  } catch (error) {
    console.error('Failed to load cases:', error);
    document.getElementById('case-select').innerHTML = '<option value="">Failed to load cases</option>';
  }
}

async function setDefaultTitle() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.title) {
      document.getElementById('title-input').placeholder = tab.title;
    }
  } catch (error) {
    console.error('Failed to get tab title:', error);
  }
}

async function captureCurrentPage() {
  const captureBtn = document.getElementById('capture-btn');
  const btnText = captureBtn.querySelector('.btn-text');
  const spinner = captureBtn.querySelector('.spinner');
  const resultDiv = document.getElementById('result');
  
  const caseId = parseInt(document.getElementById('case-select').value, 10);
  if (!caseId) {
    showResult('Please select a case', 'error');
    return;
  }
  
  captureBtn.disabled = true;
  btnText.textContent = 'Capturing...';
  spinner.classList.remove('hidden');
  resultDiv.classList.add('hidden');
  
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    let captureResult;
    try {
      captureResult = await chrome.tabs.sendMessage(tab.id, { action: 'captureHTML' });
    } catch (error) {
      if (error.message.includes('Could not establish connection')) {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content/content.js']
        });
        
        captureResult = await chrome.tabs.sendMessage(tab.id, { action: 'captureHTML' });
      } else {
        throw error;
      }
    }
    
    if (!captureResult.success) {
      throw new Error(captureResult.error || 'Failed to capture page');
    }
    
    btnText.textContent = 'Uploading...';
    
    const title = document.getElementById('title-input').value || tab.title || 'Captured Page';
    const category = document.getElementById('category-select').value;
    
    const uploadResult = await api.uploadEvidence(
      caseId,
      title,
      captureResult.html,
      tab.url,
      category
    );
    
    if (uploadResult && uploadResult.length > 0) {
      showResult('Evidence uploaded successfully!', 'success');
      
      setTimeout(() => {
        window.close();
      }, 2000);
    } else {
      throw new Error('Upload returned no results');
    }
    
  } catch (error) {
    console.error('Capture error:', error);
    showResult(error.message || 'Failed to capture page', 'error');
  } finally {
    captureBtn.disabled = false;
    btnText.textContent = 'Capture Page';
    spinner.classList.add('hidden');
  }
}

async function captureScreenshot() {
  const screenshotBtn = document.getElementById('screenshot-btn');
  const btnText = screenshotBtn.querySelector('.btn-text');
  const spinner = screenshotBtn.querySelector('.spinner');
  const resultDiv = document.getElementById('result');
  
  const caseId = parseInt(document.getElementById('case-select').value, 10);
  if (!caseId) {
    showResult('Please select a case', 'error');
    return;
  }
  
  screenshotBtn.disabled = true;
  btnText.textContent = 'Capturing...';
  spinner.classList.remove('hidden');
  resultDiv.classList.add('hidden');
  
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    const dataUrl = await chrome.tabs.captureVisibleTab(null, {
      format: 'png',
      quality: 90
    });
    
    btnText.textContent = 'Uploading...';
    
    const title = document.getElementById('title-input').value || `Screenshot - ${tab.title || 'Unknown Page'}`;
    const category = 'Other';
    
    const response = await fetch(dataUrl);
    const blob = await response.blob();
    
    const uploadResult = await api.uploadScreenshot(
      caseId,
      title,
      blob,
      tab.url,
      category
    );
    
    if (uploadResult && uploadResult.length > 0) {
      showResult('Screenshot uploaded successfully!', 'success');
      
      setTimeout(() => {
        window.close();
      }, 2000);
    } else {
      throw new Error('Upload returned no results');
    }
    
  } catch (error) {
    console.error('Screenshot error:', error);
    showResult(error.message || 'Failed to capture screenshot', 'error');
  } finally {
    screenshotBtn.disabled = false;
    btnText.textContent = 'Screenshot';
    spinner.classList.add('hidden');
  }
}

function showResult(message, type) {
  const resultDiv = document.getElementById('result');
  resultDiv.textContent = message;
  resultDiv.className = `result ${type}`;
  resultDiv.classList.remove('hidden');
}