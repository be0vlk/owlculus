# Owlculus Evidence Collector Browser Extension

A browser extension that allows you to capture web pages and send them as evidence to your Owlculus case management system.

## Features

- Capture full HTML content of web pages
- Automatic removal of scripts and sensitive data
- Direct upload to Owlculus evidence storage
- Case selection from available cases
- Configurable API endpoint
- JWT-based authentication
- Support for evidence categories

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked"
4. Select the `extension` directory from this repository

## Configuration

1. Click the extension icon and then "Open Settings"
2. Configure your Owlculus site endpoint (e.g., `http://localhost`)
3. Login with your Owlculus credentials
4. The extension will remember your authentication

## Usage

1. Navigate to any web page you want to capture
2. Click the Owlculus extension icon
3. Select a case from the dropdown
4. Optionally modify the title and category
5. Click "Capture Page"
6. The page HTML will be uploaded as evidence to the selected case

## Security Features

- Removes all JavaScript from captured pages
- Clears sensitive form data and tokens
- Uses secure Chrome storage for credentials
- JWT tokens expire according to server configuration

## Development

The extension uses Chrome Extension Manifest V3 and consists of:

- **Popup**: Main user interface for capture functionality
- **Options**: Settings page for API configuration and authentication
- **Content Script**: Captures page HTML and removes sensitive data
- **Service Worker**: Handles background operations
- **Utils**: API client and storage utilities

## API Integration

The extension integrates with Owlculus API endpoints:

- `POST /api/auth/login` - Authentication
- `GET /api/users/me` - Get current user
- `GET /api/cases/` - List available cases
- `POST /api/evidence/` - Upload evidence

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
