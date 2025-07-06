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

## Roadmap

Planned features and improvements:

- **Enhanced Plugin Library**: More OSINT tools and custom integrations
- **LLM Integration**: AI-powered analysis and insights
- **Advanced Analytics**: Cross-case patterns and timeline analysis, charts, etc.
- **API Enhancements**: Webhook support and third-party integrations
- **Cloud Deployment**: Native support for AWS, GCP, and Azure
- **Python SDK**: Making it even easier to integrate Owlculus into your flow

Open to suggestions via GitHub issues!

## Installation

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/)
and [Docker Compose](https://docs.docker.com/compose/install/)

```bash
git clone https://github.com/be0vlk/owlculus.git
cd owlculus
chmod +x setup.sh
./setup.sh
```

**Access URLs:**

- Frontend: http://localhost:8081
- Backend API: http://localhost:8000

**Setup Options:**

*Tested on Linux only. Windows users should use WSL.*

- `./setup.sh` - Standard interactive setup. If just for your personal use, you should select Local Production mode when prompted.
- `./setup.sh --clean` - Clean installation
- `./setup.sh --non-interactive` - Use defaults

If you're doing any development, you can add the `--testdata` flag to any setup mode to prepoulate some basic data for
testing with.

### Management Commands

```bash
make start-dev     # Start development services
make stop          # Stop all services
make logs          # View service logs
make test          # Run backend tests
make clean         # Remove all containers and volumes (⚠️ destroys data)
```

See `make help` for all commands.

## Browser Extension

Capture web pages directly to case evidence.

**Installation:** Load unpacked extension from `extension/` directory in Chrome developer mode.
**Usage:** Click extension icon, select case, capture page HTML.

See [extension/README.md](extension/README.md) for details.

## Quick Start

> ![Main Dashboard](https://i.ibb.co/wFMwb7WY/case-dashboard.png)

1. **Login** with admin credentials from setup
2. **Create a case** using "New Case" button, then click on it in the table to access
3. **Add entities** (person, company, domain, IP address, vehicle) which all come with templated notes
4. **Upload evidence** in the "Evidence" tab using folder templates or custom structure (right-click on an evidence item to see some options!)
5. **Run OSINT plugins** from the "Plugins" page with optional evidence saving
6. **Execute hunts** for automated multi-step investigations (WIP)

## User Roles

| Role             | Access         | Permissions                                 |
|------------------|----------------|---------------------------------------------|
| **Admin**        | All cases      | Full access, user management, system config |
| **Investigator** | Assigned cases | Read/write, run plugins, no user management |
| **Analyst**      | Assigned cases | Read-only access                            |

## Contributing

If you find the app useful and feel so inclined, please consider fueling my future coding sessions with a donation
below. Anything and everything helps and is greatly appreciated :)

GitHub Issues and Pull Requests always welcome too!

<a href="https://www.buymeacoffee.com/be0vlk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>