# Owlculus

<p align="center">
  <img src="https://i.imgur.com/Cuf4hMK.png" />
</p>

Owlculus is a comprehensive OSINT case management platform built for solo work or investigative teams. Manage cases,
collaborate, and run OSINT tools directly in your browser.

**100% free and open-source forever, no matter what.**

> **Active Development**: Note that Owlculus is under active development. Run `git pull` in the repo root regularly for
> updates. Never deploy the "
> dev" branch to production!

## Features

- **Case Management**: Create and track cases with customizable report numbering
- **Multi-User Collaboration**: Role-based access controls (Admin, Investigator, Analyst)
- **Entity System**: Track individual people, companies, domains, IP addresses, and vehicles each with dedicated
  notetaking
- **Evidence Management**: Organized file storage with folder templates and integration with the browser extension
- **OSINT Plugin Ecosystem**: Run popular open-source and custom OSINT tools right in your browser
- **Cross-Case Correlation**: Discover connections between investigations with the Correlation Scan plugin
- **Automated Hunts**: Multi-step OSINT workflows for comprehensive research (WIP)
- **Browser Extension**: Capture web pages as HTML or screenshots as you investigate and save directly to case evidence
- **RESTful API**: Complete API backend for easy automation and integrations

## Documentation

[Wiki](https://github.com/be0vlk/owlculus/wiki)

Run `make setup` for production or `make setup-dev` for development. Fresh installs generate `.env` automatically. See the commented [.env.example](.env.example) for configuration settings.

If `make setup` reports a missing `RUNTIME_POSTGRES_PASSWORD` when upgrading:

1. Run `openssl rand -hex 32` to generate a password for the new restricted database login.
2. Edit the existing `.env` in the repository root. Add `RUNTIME_POSTGRES_USER=owlculus_runtime` (different from `POSTGRES_USER`) and `RUNTIME_POSTGRES_PASSWORD=`, pasting the generated output after `=`. If that login already exists, use its existing password instead.
3. Preserve `SECRET_KEY` and all existing `POSTGRES_*` values. Save the file and rerun `make setup`.

## Contributing
GitHub Issues and Pull Requests always welcome! Oh and make sure to at least read the CONTRIBUTING.md readme first for some basic guidelines.

If you find the app useful and feel so inclined, please consider fueling my future coding sessions with a donation
below. Anything and everything helps and is greatly appreciated :)

<a href="https://www.buymeacoffee.com/be0vlk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
