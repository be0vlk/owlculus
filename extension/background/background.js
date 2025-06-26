chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'captureCurrentTab') {
    handleTabCapture(sender.tab.id).then(sendResponse);
    return true;
  }
});

async function handleTabCapture(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { action: 'captureHTML' });
    return response;
  } catch (error) {
    console.error('Error capturing tab:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

chrome.runtime.onInstalled.addListener(() => {
  console.log('Owlculus Evidence Collector extension installed');
});