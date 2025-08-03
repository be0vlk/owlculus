# Contributing Guidelines

Thank you for your interest in contributing to this project! Please follow these guidelines to help us maintain a high-quality codebase.

## Pull Request Process

- **Target Branch**: Always submit your pull requests (PRs) to the `dev` branch, _not_ the `main` branch.
- **Description**: PRs must include clear and descriptive explanations of the changes you've made. Highlight the problem solved or the feature added, and reference related issues if applicable.

## Code Style

### Backend

- Use [Black](https://black.readthedocs.io/en/stable/) for automatic code formatting.
- Use [Ruff](https://docs.astral.sh/ruff/) to ensure linting and code quality.
- Make sure your code passes all style checks before submitting your PR.

### Frontend

- Use [ESLint](https://eslint.org/) to enforce code quality and style.
- Use [Prettier](https://prettier.io/) for consistent code formatting.

### Tests

- Make sure to update existing tests in `/backend/tests` or create new tests as needed for any changes to backend functionality.
- Exact testing strategy is up to you, just get as much coverage as you can.

## Naming & Documentation

- Prefer clear and descriptive method and class names over excessive code comments. Well-named methods and classes often make code self-explanatory.
- Use module-level docstrings for Python.

## Other Guidelines

- TAKE SECURITY SERIOUSLY! Double and triple check your work and make sure you are considering security at every stage.
- Test your code thoroughly and ensure existing tests still pass.
- Be respectful and constructive in code reviews and interactions.
