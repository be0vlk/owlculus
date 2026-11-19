# Contributing Guidelines

Thank you for your interest in contributing to this project! Please follow these guidelines to help us maintain a not-terrible-quality codebase.

## Security First

- TAKE SECURITY SERIOUSLY! Owlculus stores sensitive investigation data. Double and triple check your work and consider security at every stage.
- **Never report a vulnerability in a public issue or PR.** Follow [SECURITY.md](SECURITY.md) instead.

## Prerequisites

- Docker with Docker Compose
- [uv](https://docs.astral.sh/uv/) (backend, Python 3.12)
- Node.js 24 (frontend)

## Development Setup

Start the development stack from the repository root:

```bash
make setup-dev
```

Install the local toolchains for tests and linting:

```bash
cd backend && uv sync --locked
cd frontend && npm ci
```

Enable the pre-commit hook once per clone. It runs `make lint` and the frontend unit tests your change affects:

```bash
git config core.hooksPath .githooks
```

Run `make help` to see the other commands.

## Checks

CI runs these on every PR, and a PR can't merge until they pass. Run them locally first, from the repository root:

```bash
make lint        # Ruff, ESLint, Stylelint
make typecheck   # mypy
make test        # backend tests and frontend unit tests
```

To fix formatting, run `uv run --locked ruff format app tests ../scripts` from `backend/` and `npm run format` from `frontend/`.

## Tests

Add or update tests for every behavior change. Exact testing strategy is up to you, just get as much coverage as you can.

- **Backend**: pytest, under `backend/tests/`.
- **Frontend**: Vitest, in `__tests__/` folders next to the code they cover.
- **Browser**: Playwright journeys, under `frontend/e2e/`.

CI doesn't run the browser journeys. Run them yourself when you change a user-facing workflow:

```bash
make test-browser
```

To run one backend file: `cd backend && uv run --locked pytest tests/path/to/test_file.py`.

The durable execution tests in `backend/tests/executions/` skip by default. They start disposable PostgreSQL and Redis containers and take about 10 minutes. Run them when you change plugin or hunt execution:

```bash
cd backend && RUN_EXECUTION_ACCEPTANCE=1 uv run --locked pytest tests/executions
```

## Plugins and Hunts

Generate the boilerplate for a new plugin or hunt instead of writing it by hand:

```bash
python scripts/create_plugin.py <plugin_name>
python scripts/create_hunt.py <hunt_name>
```

Run either script with `--help` for its options.

## Pull Request Process

- Open PRs against `main`.
- Fill in the PR template: a summary of the change, evidence that it works, and how risky it is to merge.
- If your change affects what users see or do (setup, configuration, features), say so in the PR so the [wiki](https://github.com/be0vlk/owlculus/wiki) can be updated.

## Naming & Documentation

- Prefer clear and descriptive method and class names over excessive code comments. Well-named methods and classes often make code self-explanatory.
- Use module-level docstrings in Python.

## Conduct

- Be respectful and constructive in code reviews and interactions.
