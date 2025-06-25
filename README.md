# Owlculus

<p align="center">
  <img src="https://i.imgur.com/Cuf4hMK.png" />
</p>

Owlculus is a comprehensive OSINT case management platform built for solo work or investigative teams. Manage cases, collaborate, and run OSINT tools directly in your browser.

This project is now and will always be 100% free and open-source, no matter how much it improves.

## Active Development Notice

Owlculus is under active development with frequent updates, improvements, and new features being added regularly. To ensure you have the latest features and security updates, please:

1. **Check for updates** by pulling the latest changes from the repository:
   ```bash
   git pull origin main
   ```
2. **Review the changelog** for recent updates and breaking changes
3. **Watch the repository** on GitHub to receive notifications about new releases and updates
4. **Check the Roadmap section** below for upcoming features and changes

**IMPORTANT**: Never deploy the "dev" branch to a production environment!

## Features

### Core Platform
- **Case Management**: Create and track cases with customizable report number formats
- **Multi-User Collaboration**: Role-based permissions (Admin, Investigator, Analyst)
- **RESTful API**: Comprehensive backend for automation and integrations
- **Rich Text Editing**: Note editor with formatting and organization
- **Evidence Management**: Organized file storage with optional automatic folder structures
- **Entity System**: Assign various types of entities to your case each with templated, self-contained notes
- **Cross-Case Correlation**: Automatically discover connections between investigations (WIP)

### OSINT Plugin Ecosystem
Allows running popular and custom OSINT tools right within the app.

- **Extensible Framework**: Built on a modular architecture for straightforward custom tool integration
- **Optional Evidence Saving**: Plugin results can be directly saved to case evidence folders

### System Features
- **Configurable Case Numbers**: Customizable templates (YYMM-NN, PREFIX-YYMM-NN)
- **Dark/Light Mode**: User preference themes
- **Manage Evidence Storage Templates**: Allows you to quickly apply folder structures from templates

## Roadmap

I will be very actively maintaining and improving this application and am always open to suggestions. If you have any of those, or come across any bugs, please feel free to open an issue right here on GitHub. Some things definitely planned are:

- **Enhanced Plugin Library**: More OSINT tools and custom integrations
- **Evidence Automation**: Browser extensions and automated collection workflows
- **LLM Integration**: AI-powered analysis and insights (StrixyChat integration planned)
- **Advanced Analytics**: Cross-case patterns, timeline analysis, and reporting dashboards
- **API Enhancements**: Webhook support and third-party integrations
- **Cloud-based Deployment**: Native support for cloud platforms like AWS, GCP, and Azure

## Installation

Owlculus uses Docker for easy, consistent installation. The Docker setup handles all dependencies, database configuration, and service orchestration automatically.

It is technically cross-platform thanks to Docker, but I have only tested on Debian/Ubuntu Linux distros. The setup script is also Linux only. If you must be on Windows, I would *strongly* suggest at least using WSL.

### Quick Start

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

1. Clone the repository:
```bash
git clone https://github.com/be0vlk/owlculus.git
cd owlculus
```

2. Run the interactive setup:
```bash
chmod +x setup.sh
./setup.sh
```

The setup script will guide you through configuration options.

After setup, Owlculus will be available at your configured URLs (defaults shown). If you are just running this locally, I recommend leaving the defaults:
- **Frontend:** http://localhost
- **Backend API:** http://localhost:8000
- **Login:** Your configured admin credentials

### Setup Options

**Interactive setup (default):**
```bash
./setup.sh                    # Production mode with interactive configuration
./setup.sh dev                # Development mode with interactive configuration
```

**Non-interactive setup:**
```bash
./setup.sh --non-interactive         # Uses all defaults
./setup.sh dev --non-interactive     # Development mode with defaults
```

**Clean installation:**
```bash
./setup.sh --clean                   # Remove all Owlculus Docker artifacts first
./setup.sh dev --clean               # Clean development setup
```

**Verbose output:**
```bash
./setup.sh --verbose                 # Shows full Docker build output
./setup.sh dev --verbose             # Development with verbose output
```

### Development Setup

Development mode includes:
- **Frontend:** http://localhost:5173 (with hot-reload)
- **Backend API:** http://localhost:8000 (with hot-reload)
- Source code mounted as volumes for instant updates

### Management Commands

Use the included Makefile for easy management:

```bash
make help          # Show all available commands
make setup         # Initial setup (production)
make setup-dev     # Initial setup (development)
make start         # Start production services
make start-dev     # Start development services
make stop          # Stop all services
make restart       # Restart all services
make logs          # View service logs
make build         # Build Docker images
make rebuild       # Rebuild images (no cache)
make test          # Run backend tests
make shell-backend # Open backend container shell
make shell-db      # Open database shell
make status        # Show service status
make clean         # Remove all containers and volumes (⚠️ destroys data)
```

## Troubleshooting

### Common Issues

**Services won't start:**
```bash
# Check if ports are already in use
sudo netstat -tulpn | grep -E ':80|:8000|:5432'

# View service logs
docker compose logs

# Rebuild images if needed
docker compose build --no-cache
```

**Database connection issues:**
```bash
# Check PostgreSQL container health
docker compose ps

# Reset database (⚠️ destroys all data)
docker compose down -v
docker compose up -d
```

**Permission errors on Linux:**
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
chmod +x setup.sh
```

**Can't access the application:**
- Ensure Docker containers are running: `docker compose ps`
- Check firewall settings if accessing remotely
- Wait 30-60 seconds for all services to fully start

### Getting Help

If you encounter issues:
1. Check the [troubleshooting section](#troubleshooting) above
2. Review service logs: `docker compose logs -f`
3. Open an issue on GitHub with logs and error details when possible

## Usage

### Case Dashboard
After logging in as the admin user, you'll be redirected to the main case dashboard where you can create your first case by clicking the aptly named "New Case" button. A modal will pop up asking for basic case details. Optionally, before you create the case, click "Clients" in the sidebar to add a client which you will then be able to add the case to. The database initialization script will have already created a client called "Personal" for any cases you are not working for a real client.

**NOTE**: Non-admin users cannot interact with any cases they are not explicitly assigned to, and only admins can assign them. Cases that a user is not assigned to will not show up in the dashboard and will not be accessible via the API.

Now, double-click directly on the case in the table and you'll be redirected to that case's detail page.

### Case Detail
This page displays the basic case information and allows you to create and view notes, upload/download evidence to the case folder, add users to the case, create entities (more on that below) and update the case status. When you first create a case, you will not see the entity tabs so don't worry if your screen looks a little different at first.

#### Entities
This is a key part of Owlculus functionality. Rather than defining case types upfront, you add individual entities to build your investigation dynamically. The system supports flexible entity types including `person`, `company`, `vehicle`, `domain`, and `ip_address`, with JSON-based data storage allowing for extensible schemas.

**Entity Features:**
- **Template-Based Notes**: Each entity type comes with predefined, organized note templates
- **Category-Based Organization**: Each entity type has its own set of categories in the form of tabs within the entity
- **Rich Text Editing**: TipTap-powered notes with basic formatting options
- **Smart Relationships (WIP)**: Automatic entity linking and relationship detection within the same case
- **Cross-Case Visibility**: Entities can be discovered across multiple cases through the correlation scanning plugin

#### Evidence
This page allows you to upload and download evidence to the case folder. Cases are initially created with no folder structure but the app comes with pre-configured templates that can be applied. Admin users can also create new templates within the Admin dashboard.

### Plugins
This page allows you to conveniently run a variety of OSINT tools right from the app.

#### Correlation Plugin
This plugin will scan for correlations between entities in cases.

**NOTE:** This will only reveal correlations between cases that are assigned to the current user. Hypothetically, there could still be cases that are not assigned to the user but have a correlation. Admins have access to everything.

### System Configuration
Administrators can customize system-wide settings through the Admin dashboard.

### User Roles & Permissions

**Admin**
- Full access to all system features and data
- Create and manage cases, clients, and users
- Run all plugins and access all case data
- Configure system settings and case number formats

**Investigator** 
- Standard read/write access to assigned cases
- Create and edit notes, upload evidence
- Run plugins and analysis tools
- Cannot create cases or manage users

**Analyst**
- Read-only access to assigned cases
- View notes and download evidence
- Cannot edit data or run plugins
- Cannot create cases or manage users
