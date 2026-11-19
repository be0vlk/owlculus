# Security Policy

## Supported Versions

Owlculus is under heavy active development. Security fixes go into the latest release on `main` only.

| Version          | Supported |
| ---------------- | --------- |
| 2.1.x (latest)   | ✅        |
| < 2.1            | ❌        |
| `dev` branch     | ❌        |

To get fixes, run `git pull` in the repo root, then `make setup`.

## Reporting a Vulnerability

**Do not open a public issue, PR, or discussion for security problems.**

Report them privately through GitHub's
[private vulnerability reporting](https://github.com/be0vlk/owlculus/security/advisories/new)
(the **Security** tab → **Report a vulnerability**).

Please include:

- The affected component: backend API, frontend, browser extension, plugin system, or setup/deployment scripts
- The version or commit hash
- Steps to reproduce, or a proof of concept
- The impact you expect, such as cross-case data access, privilege escalation between roles, or remote code execution
- Any fix you suggest (optional)

## What to Expect

- **Acknowledgement** within 7 days
- **Initial assessment** within 14 days
- I'll keep you updated as I work on a fix and coordinate a disclosure date with you.
  The usual target is a fix within 30 days of the report.
- If you'd like credit, you'll be named in the GitHub Security Advisory and the release notes.

Keep in mind I'm just one guy over here, so these timelines are goals rather than guarantees.

## Scope

**In scope**

- Authentication, sessions, and role-based access control (Admin / Investigator / Analyst)
- Access to cases, entities, or evidence that a user shouldn't be able to reach
- File upload and evidence storage handling
- Plugin and hunt execution, including command or argument injection
- The browser extension and its communication with the backend
- Insecure defaults in `setup.sh`, `docker-compose.yml`, or the generated `.env`

**Out of scope**

- Vulnerabilities in third-party tools that plugins wrap. Report those upstream.
- Problems that only exist in deployments that ignore the docs, such as running the `dev` branch or dev compose file in production, or exposing the database publicly
- Missing best-practice headers or hardening that has no demonstrated impact
- Denial of service through resource exhaustion on a self-hosted instance
- Social engineering, and physical attacks on infrastructure

## Safe Harbor

Good-faith research on your **own** Owlculus instance is welcome. 
Don't test against instances you don't own, and don't access, change, or keep other people's investigation data.
