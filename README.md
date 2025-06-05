# Owlculus

<p align="center">
  <img src="https://i.imgur.com/Cuf4hMK.png" />
</p>

Owlculus is purpose built for managing OSINT investigation cases and running useful tools right in the browser.

**NOTE:** This project is now and will always be 100% free and open-source, no matter how much it improves. If you're feeling generous, donate to your favorite charity instead :)

## Features
- Create and track cases with preset report number formats.
- Web-based multi-user collaboration with predefined roles for different permissions.
- The backend RESTful API architecture enables various types of automation and integration.
- Run useful OSINT tools right in the app and associate results with cases.
- Automatically scan for correlations between cases. Investigated John Doe two months ago in a different case? The scan will find it.

## Roadmap
I will be very actively maintaining and improving this application and am always open to suggestions. If you have any of those, or come across any bugs, please feel free to open an issue right here on GitHub. Some things definitely planned are:

- More custom built and open-source tool compatibility on the plugins dashboard
- Different ways to add evidence to case files (browser extension?)
- Powerful LLM integration
- More robust analytics and other helpful insights

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
make start         # Start production services
make start-dev     # Start development services
make stop          # Stop all services
make logs          # View service logs
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
This is a key part of Owlculus functionality. Rather than define the case type when you create it, like we did in the previous version, you now add individual entities to the case. For now, the only entity types are `person`, `company`, `domain` and `ip_address`. Each entity is its own standalone component and each type comes with predefined templates for note-taking.

When you first create an entity, only some of the template will show up. After you create it, you can click the "View Details" button to expand it. This will show you the full template and allow you to add several additional notes, all conveniently organized by category.

The app is smart enough to recognize certain relationships between entities and automatically create/link them. For example, if you create a person entity for John Doe and add "Jane Doe" as his sister within his notes, a new entity will be created for Jane Doe and automatically linked to John. This will be much more robust in the future but try it out!

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

### Admin
Basic admin portal that allows you to create, manage and delete users.

`Admin` Full access to do anything in the app, including run all plugins, view and edit any case/client, etc.

`Investigator` Standard read/write access to any cases they have been assigned to. This includes editing notes and running the various plugins offered in app. They cannot create cases.

`Analyst` Essentially, read-only access. They can review notes and download evidence from any case they are assigned to, but have no access to any write operations or plugin runs.
