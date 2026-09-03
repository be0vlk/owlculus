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

### First-run setup

For a local production installation, run:

```bash
./setup.sh --non-interactive
```

When the services are ready, retrieve the one-time setup token from the backend:

```bash
docker compose logs backend
```

Open [http://localhost/setup](http://localhost/setup). Owlculus routes every fresh
installation to `/setup`, where you enter the token and choose the username, email,
and password for the first administrator. The setup script does not create or print
administrator credentials.

If the backend restarts before setup is complete, the same setup token remains valid
and can be retrieved from the logs again. After the administrator is created, the
token is consumed: use the normal login page on this and subsequent starts. When an
upgraded installation already has users, setup is skipped and no setup token is
created.

The default gateway listens on port 80 without restricting the hostname, so the site
also works through `127.0.0.1`, a LAN address, or another local hostname. Browser API
and WebSocket requests remain same-origin through Caddy. To use a public hostname,
set `DOMAIN` in `.env`; Caddy will serve that hostname and manage HTTPS automatically:

```dotenv
DOMAIN=owlculus.example.com
```

To remove containers, images, volumes, and local configuration before rebuilding,
run `./setup.sh --clean --non-interactive`. This permanently removes local Owlculus
state.

After creating the administrator, development test data can be loaded with credentials
chosen by the operator:

```bash
./scripts/run_test_data.sh --username YOUR_USERNAME
```

The helper prompts for the administrator password without placing it in shell history.

More documentation is hosted in the [GitHub Wiki](https://github.com/be0vlk/owlculus/wiki).
If you need additional guidance, please open a [Discussion](https://github.com/be0vlk/owlculus/discussions).

## Contributing
GitHub Issues and Pull Requests always welcome! Oh and make sure to at least read the CONTRIBUTING.md readme first for some basic guidelines.

If you find the app useful and feel so inclined, please consider fueling my future coding sessions with a donation
below. Anything and everything helps and is greatly appreciated :)

<a href="https://www.buymeacoffee.com/be0vlk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
