# Owlculus

<p align="center">
  <img src="https://i.imgur.com/Cuf4hMK.png" />
</p>

Owlculus is a comprehensive OSINT case management platform built for solo work or investigative teams. Manage cases, collaborate, and run OSINT tools directly in your browser.

**Version 1.0.0** - Stable

**NOTE:** This project is now and will always be 100% free and open-source, no matter how much it improves. If you're feeling generous, donate to your favorite charity instead :)

## Features

### Core Platform
- **Case Management**: Create and track cases with customizable report number formats
- **Multi-User Collaboration**: Role-based permissions (Admin, Investigator, Analyst)
- **RESTful API**: Comprehensive backend for automation and integrations
- **Rich Text Editing**: Note editor with formatting and organization
- **Evidence Management**: Organized file storage with automatic folder structures
- **Entity System**: Assign various types of entities to your case each which templated, self-contained notes
- **Cross-Case Correlation**: Automatically discover connections between investigations (WIP)

### OSINT Plugin Ecosystem
- **DNS Lookup Plugin**: Comprehensive DNS reconnaissance (A, AAAA, MX, NS, TXT, CNAME records)
- **Holehe Plugin**: Email address reconnaissance across 120+ social platforms
- **Correlation Scanner**: Intelligent cross-case entity matching and relationship discovery
- **Extensible Framework**: Built on a modular architecture for straightforward custom tool integration
- **Optional Evidence Saving**: Plugin results can be directly saved to case evidence folders

### System Features
- **Configurable Case Numbers**: Customizable templates (YYMM-NN, PREFIX-YYMM-NN)
- **Dark/Light Mode**: User preference themes
- **Real-time Updates**: Live plugin execution with streaming results

## Technology Stack

**Backend:**
- FastAPI with SQLModel
- PostgreSQL database
- JWT authentication
- Docker containerization

**Frontend:**
- Vue 3.5.13 with Composition API
- Vuetify 3.7.3 (Material Design)
- Pinia state management
- TipTap rich text editor
- Vite build system

**Testing & Development:**
- Playwright E2E testing
- Vitest unit testing
- ESLint + Prettier
- Hot-reload development

## Roadmap

I will be very actively maintaining and improving this application and am always open to suggestions. If you have any of those, or come across any bugs, please feel free to open an issue right here on GitHub. Some things definitely planned are:

- **Enhanced Plugin Library**: More OSINT tools and custom integrations
- **Evidence Automation**: Browser extensions and automated collection workflows
- **LLM Integration**: AI-powered analysis and insights (StrixyChat integration planned)
- **Advanced Analytics**: Cross-case patterns, timeline analysis, and reporting dashboards
- **API Enhancements**: Webhook support and third-party integrations

## Installation

Owlculus uses **Docker for easy, consistent installation** on any platform (Linux, macOS, Windows). The Docker setup handles all dependencies, database configuration, and service orchestration automatically.

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

The setup script will guide you through configuration options:
- **Network settings:** Domain, frontend port (default: 80), backend port (default: 8000), database port (default: 5432)
- **Admin account:** Username (default: admin), email, password (auto-generated if not provided)

After setup, Owlculus will be available at your configured URLs (defaults shown):
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

## Environment Configuration

The setup script automatically creates a `.env` file with your configuration and secure auto-generated credentials. You can view your credentials anytime:

```bash
cat .env
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
![Imgur](https://i.imgur.com/LqT2jQf.png)

After logging in as the admin user, you'll be redirected to the main case dashboard where you can create your first case by clicking the aptly named "New Case" button. A modal will pop up asking for basic case details. Optionally, before you create the case, click "Clients" in the sidebar to add a client which you will then be able to add the case to. The database initialization script will have already created a client called "Personal" for any cases you are not working for a real client.

**NOTE**: Non-admin users cannot interact with any cases they are not explicitly assigned to, and only admins can assign them. Cases that a user is not assigned to will not show up in the dashboard and will not be accessible via the API.

Now, double-click directly on the case in the table and you'll be redirected to that case's detail page.

### Case Detail
![Imgur](https://i.imgur.com/o5XjCc5.png)

This page displays the basic case information and allows you to create and view notes, upload/download evidence to the case folder, add users to the case, create entities (more on that below) and update the case status. When you first create a case, you will not see the entity tabs so don't worry if your screen looks a little different at first.

#### Entities
This is a key part of Owlculus functionality. Rather than defining case types upfront, you add individual entities to build your investigation dynamically. The system supports flexible entity types including `person`, `company`, `domain`, and `ip_address`, with JSON-based data storage allowing for extensible schemas.

**Entity Features:**
- **Template-Based Notes**: Each entity type comes with predefined, organized note templates
- **Expandable Views**: Start with essential fields, expand to detailed templates as needed
- **Rich Text Editing**: TipTap-powered notes with formatting, links, and structure
- **Smart Relationships**: Automatic entity linking and relationship detection
- **Cross-Case Visibility**: Entities can be discovered across multiple cases through correlation scanning

When you create an entity, you'll see a streamlined interface initially. Use "View Details" to access the full template with categorized note sections. The system intelligently recognizes relationships—mentioning "Jane Doe" in John Doe's family notes can automatically create and link a new Jane Doe entity.

#### Evidence

![Imgur](https://i.imgur.com/OVFMt6o.png)
This page allows you to upload and download evidence to the case folder. A default, organized virtual folder structure is created along with the case.

### Plugins
This page allows you to conveniently run certain OSINT tools right from the app.

#### Correlation Plugin
This plugin will scan for correlations between entities in cases.

![Imgur](https://i.imgur.com/cKtoJya.png)

In this example, the match came up because John Doe and Billy Bob both have "Acme Co" listed as their employer in their respective cases. Output from this plugin is also automatically added to the case's evidence folder.

**NOTE:** This will only reveal correlations between cases that are assigned to the current user. Hypothetically, there could still be cases that are not assigned to the user but have a correlation. Admins have access to everything.

### System Configuration
Administrators can customize system-wide settings through the Settings page:

**Case Number Configuration:**
- **Templates**: Choose from preset formats (YYMM-NN, PREFIX-YYMM-NN)
- **Custom Prefixes**: Set organization-specific prefixes for case numbers
- **Auto-Incrementing**: Automatic sequential numbering within each format

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
