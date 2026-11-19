# Owlculus Evidence Collector Browser Extension

A browser extension that captures web pages as HTML or screenshots and saves them as Evidence in an Owlculus Case.

## Features

- Save the full HTML of a page, with scripts and sensitive form data removed
- Take a screenshot of the visible part of the tab (not the full scrollable page)
- Upload directly to a chosen Case and Evidence folder
- Configurable Owlculus site URL, with sessions bound to that instance
- Token-based authentication against the Owlculus API

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked"
4. Select the `extension` directory from this repository

## Configuration

1. Click the extension icon and then **Open Settings**
2. Enter the **Owlculus Site URL** (e.g., `http://localhost`, `http://localhost:5173` for development, or `https://owlculus.example.com`)
3. Move focus out of the URL field and grant the requested site permission
4. Enter your **Username** and **Password** and click **Login**
5. The extension remembers your session for that site

## Usage

1. Navigate to any web page you want to capture
2. Click the Owlculus extension icon
3. Choose a Case in **Select Case** and a folder in **Save to Folder**
4. Optionally edit the **Evidence Title**
5. Click **Save Page** to upload the page HTML, or **Screenshot** to upload an image of the visible tab
6. The capture is saved as Evidence in the selected Case and folder

## Security Features

- Removes all JavaScript from captured pages
- Clears sensitive form data and tokens
- Stores credentials encrypted in extension storage
- JWT tokens expire according to server configuration

## Development

The extension uses Chrome Extension Manifest V3 and consists of:

- **Popup**: Main user interface for capture functionality
- **Options**: Settings page for API configuration and authentication
- **Content Script**: Captures page HTML and removes scripts and sensitive data
- **Service Worker**: Handles background operations
- **Utils**: API client and storage utilities

## API Integration

The extension integrates with Owlculus API endpoints:

- `POST /api/auth/login` - Authentication
- `GET /api/users/me` - Get current user
- `GET /api/cases/` - List available cases
- `GET /api/evidence/case/{case_id}/folder-tree` - List a Case's folders
- `POST /api/evidence/` - Upload evidence (HTML or screenshot)

## Requirements

- Chrome browser (or Chromium-based browser)
- Running Owlculus backend instance
- Valid Owlculus user account with appropriate permissions

## Troubleshooting

- If authentication fails, check that your API endpoint is correct
- Ensure your Owlculus backend is running and accessible
- Check browser console for detailed error messages
- Make sure you have at least one case created in Owlculus

### Instance-bound sessions

Credentials, cached user details, and the last selected Case belong to the endpoint
that issued the login response. Switching instances clears that session and requires
sign-in. Existing installations with unbound legacy credentials must sign in again.
Denied host permission and invalid URLs retain the previous selection and session.
An already open popup clears its instance data on a session change; reopen it to
load the newly selected instance.

Endpoint identity uses the browser URL parser: scheme/hostname case, default ports
(`:80` for HTTP, `:443` for HTTPS), dot segments, and trailing slashes are normalized.
Scheme, non-default port, and base path (including path case) remain significant.
For example, `https://EXAMPLE.com:443/team/` equals `https://example.com/team`,
but differs from `http://example.com/team` and `https://example.com/other`.
Credentials, queries, and fragments in endpoint URLs are rejected. Authenticated
requests cannot follow redirects; configure the final instance URL directly.

Session mutations use Web Locks across extension contexts. Each request retains
one endpoint/session snapshot, and responses from an obsolete session are rejected.
The focused memory-only regressions run with:

```sh
cd frontend
npm run test:unit -- --run src/__tests__/extensionSession.test.js
```
