#!/bin/bash

# Owlculus Docker Setup Script
# Interactive deployment setup

# Colors for output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if ! command_exists docker; then
    print_status "Docker not found. Installing..."
    sudo apt-get update
    sudo apt-get install -qq -y docker.io
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
    print_success "Docker installed successfully"
else
    print_success "Docker is already installed"
fi

if docker compose version &>/dev/null; then
    print_success "Docker Compose is already installed"
else
    print_status "Docker Compose not found. Installing..."
    
    sudo apt-get update
    sudo apt-get install -qq -y docker-compose-v2
    
    if docker compose version &>/dev/null; then
        print_success "Docker Compose installed successfully"
    else
        print_error "Failed to install Docker Compose v2"
        exit 1
    fi
fi

if ! command_exists python3; then
    print_status "Python 3 not found. Installing..."
    sudo apt-get update
    sudo apt-get install -qq -y python3
    print_success "Python 3 installed successfully"
else
    print_success "Python 3 is already installed"
fi



# Default configuration values
DEFAULT_FRONTEND_PORT=80
DEFAULT_BACKEND_PORT=8000
DEFAULT_DB_PORT=5432
DEFAULT_DOMAIN="localhost"

# Configuration variables
FRONTEND_PORT=""
BACKEND_PORT=""
DB_PORT=""
DOMAIN=""
CADDY_DOMAIN=""
USE_REVERSE_PROXY="false"
USE_HTTPS="false"
INTERACTIVE_MODE="true"
DEPLOYMENT_TYPE=""
COMPOSE_SCRIPT="./scripts/compose.sh"
DIRECT_TOPOLOGY="direct"
DEV_TOPOLOGY="development"
REVERSE_PROXY_TOPOLOGY="reverse-proxy"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to generate random secret key
generate_secret_key() {
    if command_exists openssl; then
        openssl rand -hex 32
    elif command_exists python3; then
        python3 -c "import secrets; print(secrets.token_hex(32))"
    else
        # Fallback to a basic method
        date +%s | sha256sum | base64 | head -c 32
    fi
}

# Function to prompt for user input with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    
    echo -n "$prompt [$default]: " >&2
    read value
    
    if [ -z "$value" ]; then
        echo "$default"
    else
        echo "$value"
    fi
}

# Function to validate port number
validate_port() {
    local port="$1"
    if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]; then
        return 0
    else
        return 1
    fi
}

# Derive operator-facing URLs without changing the browser's same-origin contract.
configure_service_urls() {
    if [ "$DEPLOYMENT_TYPE" = "remote" ]; then
        FRONTEND_URL="https://$DOMAIN"
    elif [ "$USE_REVERSE_PROXY" = "true" ]; then
        if [ "$USE_HTTPS" = "true" ]; then
            FRONTEND_URL="https://$DOMAIN"
        else
            FRONTEND_URL="http://$DOMAIN"
        fi
    else
        FRONTEND_URL="http://$DOMAIN:$FRONTEND_PORT"
        if [ "$FRONTEND_PORT" = "80" ]; then
            FRONTEND_URL="http://$DOMAIN"
        fi
    fi
}

# Function to run interactive configuration
interactive_config() {
    local MODE="$1"
    echo ""
    echo "Owlculus Interactive Setup"
    echo "=========================="
    echo ""
    
    # First, determine the deployment type
    echo "Select deployment type:"
    echo "---------------------"
    echo "1) Local development (with hot-reload)"
    echo "2) Local production (direct access with ports)"
    echo "3) Remote server (HTTPS with automatic certificates)"
    echo ""
    
    while true; do
        echo -n "Choose deployment type [1-3]: "
        read deployment_choice
        case $deployment_choice in
            1)
                DEPLOYMENT_TYPE="local_dev"
                MODE="dev"
                break
                ;;
            2)
                DEPLOYMENT_TYPE="local_prod"
                MODE="production"
                break
                ;;
            3)
                DEPLOYMENT_TYPE="remote"
                MODE="production"
                USE_REVERSE_PROXY="true"
                USE_HTTPS="true"
                break
                ;;
            *)
                print_error "Please enter 1, 2, or 3"
                ;;
        esac
    done
    
    echo ""
    
    # Configure based on deployment type
    if [ "$DEPLOYMENT_TYPE" = "remote" ]; then
        echo "Remote Server Configuration:"
        echo "---------------------------"
        
        while true; do
            DOMAIN=$(prompt_with_default "Domain name (e.g., owlculus.example.com)" "owlculus.example.com")
            if [ -n "$DOMAIN" ] && [[ "$DOMAIN" != "localhost" ]]; then
                CADDY_DOMAIN="$DOMAIN"
                break
            fi
            print_error "Please enter a valid domain name (not localhost)"
        done
        
        # Set internal ports - not exposed to host
        FRONTEND_PORT="80"
        BACKEND_PORT="8000"
        DB_PORT="5432"
        
        print_status "Services will be accessible via HTTPS at https://$DOMAIN"
        print_status "Caddy will automatically obtain Let's Encrypt certificates"
        
    else
        # Local deployment configuration - use defaults without prompting
        echo "Local Configuration:"
        echo "-------------------"
        
        # Set defaults based on mode
        local DEFAULT_FE_PORT="$DEFAULT_FRONTEND_PORT"
        if [ "$MODE" = "dev" ]; then
            DEFAULT_FE_PORT="5173"
        fi
        
        # Use localhost defaults for local deployments
        DOMAIN="$DEFAULT_DOMAIN"
        CADDY_DOMAIN=""
        FRONTEND_PORT="$DEFAULT_FE_PORT"
        BACKEND_PORT="$DEFAULT_BACKEND_PORT"
        
        # Database port is not exposed for security
        DB_PORT="5432"
        
        print_status "Using localhost defaults:"
        print_status "  Domain: $DOMAIN"
        print_status "  Frontend port: $FRONTEND_PORT"
        if [ "$DEPLOYMENT_TYPE" = "local_dev" ]; then
            print_status "  Backend port: $BACKEND_PORT (development only)"
        else
            print_status "  Backend API: Same origin through Caddy"
        fi
        print_status "  Database: Internal port 5432 (not exposed to host for security)"
        
        USE_REVERSE_PROXY="false"
        USE_HTTPS="false"
    fi
    
    configure_service_urls
    
    echo ""
    echo "Configuration Summary:"
    echo "====================="
    
    case "$DEPLOYMENT_TYPE" in
        "local_dev")
            echo "Deployment Type: Local Development (with hot-reload)"
            ;;
        "local_prod")
            echo "Deployment Type: Local Production"
            ;;
        "remote")
            echo "Deployment Type: Remote Server (HTTPS)"
            ;;
    esac
    
    if [ "$DEPLOYMENT_TYPE" = "remote" ]; then
        echo "Domain: $DOMAIN"
        echo "URL: https://$DOMAIN"
        echo "HTTPS: Automatic via Let's Encrypt"
        echo "Note: All services accessible through single HTTPS endpoint"
    else
        echo "Domain: $DOMAIN"
        echo "Frontend URL: $FRONTEND_URL"
        echo "Frontend Port: $FRONTEND_PORT"
        if [ "$DEPLOYMENT_TYPE" = "local_dev" ]; then
            echo "Backend Port: $BACKEND_PORT (development only)"
        fi
    fi
    echo "Database: Internal only (not exposed)"
    echo ""
    
    while true; do
        echo -n "Proceed with this configuration? [y/N]: "
        read confirm
        case $confirm in
            [Yy]|[Yy][Ee][Ss]) break ;;
            [Nn]|[Nn][Oo]|"") 
                echo "Setup cancelled by user"
                exit 0
                ;;
            *) echo "Please answer yes or no" ;;
        esac
    done
}

# Function to show usage
show_usage() {
    echo "Owlculus Docker Setup"
    echo
    echo "Usage: $0 [mode] [options]"
    echo
    echo "Modes:"
    echo "  production      Production setup (default)"
    echo "  dev             Development setup with hot-reload"
    echo "  help            Show this help message"
    echo
    echo "Options:"
    echo "  --verbose       Show all Docker build/start output"
    echo "  --non-interactive  Use default values without prompting"
    echo "  --clean         Remove all Owlculus Docker containers, images, and volumes before setup"
    echo
    echo "Interactive Setup Options:"
    echo "  1. Local development - Hot-reload enabled for development"
    echo "  2. Local production - Direct access with custom ports"
    echo "  3. Remote server - HTTPS with automatic certificates (recommended for servers)"
    echo
    echo "Examples:"
    echo "  $0                          # Interactive setup (choose deployment type)"
    echo "  $0 dev                      # Interactive development setup"
    echo "  $0 --non-interactive        # Non-interactive local production setup"
    echo "  $0 dev --verbose            # Development setup with full Docker output"
    echo "  $0 --clean                  # Clean setup (removes Owlculus Docker artifacts)"
    echo
    echo "Requirements:"
    echo "  - Docker"
    echo "  - Docker Compose"
    echo
}

# Function to clean Owlculus Docker artifacts
clean_docker_artifacts() {
    print_warning "Cleaning up Owlculus Docker artifacts..."
    
    # Stop and remove containers for both production and dev
    if "$COMPOSE_SCRIPT" "$DIRECT_TOPOLOGY" ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping production containers..."
        "$COMPOSE_SCRIPT" "$DIRECT_TOPOLOGY" down 2>/dev/null || true
    fi
    
    if "$COMPOSE_SCRIPT" "$DEV_TOPOLOGY" ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping development containers..."
        "$COMPOSE_SCRIPT" "$DEV_TOPOLOGY" down 2>/dev/null || true
    fi
    
    # Remove Owlculus volumes
    print_status "Removing Owlculus volumes..."
    docker volume ls -q | grep -E "^owlculus_" | while read volume; do
        print_status "Removing volume: $volume"
        docker volume rm "$volume" 2>/dev/null || true
    done
    
    # Remove Owlculus images
    print_status "Removing Owlculus images..."
    docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "^owlculus-" | while read image; do
        print_status "Removing image: $image"
        docker rmi "$image" 2>/dev/null || true
    done
    
    # Remove any dangling Owlculus-related containers
    docker ps -a --format "{{.Names}}" | grep -E "^owlculus-" | while read container; do
        print_status "Removing container: $container"
        docker rm -f "$container" 2>/dev/null || true
    done
    
    # Remove .env files
    if [ -f .env ]; then
        print_status "Removing .env file..."
        rm .env
    fi
    
    if [ -f frontend/.env ]; then
        print_status "Removing frontend/.env file..."
        rm frontend/.env
    fi
    
    print_success "Owlculus Docker artifacts cleaned up!"
    echo
}

# Function to set defaults for non-interactive mode
set_defaults() {
    local MODE="$1"
    
    # For non-interactive mode, default to local production
    DEPLOYMENT_TYPE="local_prod"
    
    local DEFAULT_FE_PORT="$DEFAULT_FRONTEND_PORT"
    
    # Adjust default frontend port for dev mode
    if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
        DEFAULT_FE_PORT="5173"
        DEPLOYMENT_TYPE="local_dev"
    fi
    
    DOMAIN="$DEFAULT_DOMAIN"
    CADDY_DOMAIN=""
    FRONTEND_PORT="$DEFAULT_FE_PORT"
    BACKEND_PORT="$DEFAULT_BACKEND_PORT"
    DB_PORT="$DEFAULT_DB_PORT"
    USE_REVERSE_PROXY="false"
    USE_HTTPS="false"
    
    configure_service_urls
    
}

# Main setup function
setup_owlculus() {
    local MODE="${1:-production}"
    local VERBOSE="${2:-false}"
    local CLEAN="${3:-false}"
    
    # Run cleanup if requested
    if [ "$CLEAN" = "true" ]; then
        clean_docker_artifacts
    fi
    
    print_status "Setting up Owlculus with Docker..."
    
    # Check if Docker is installed
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first:"
        echo ""
        echo "📖 Installation guides:"
        echo "  • Linux:   https://docs.docker.com/engine/install/"
        echo "  • macOS:   https://docs.docker.com/docker-for-mac/install/"
        echo "  • Windows: https://docs.docker.com/docker-for-windows/install/"
        echo ""
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! docker compose version >/dev/null 2>&1; then
        print_error "Docker Compose v2 is not available. Please install the Docker Compose plugin."
        exit 1
    fi

    DOCKER_COMPOSE_CMD="$COMPOSE_SCRIPT"
    
    print_status "Docker and Docker Compose are available"
    
    # Run interactive configuration or use defaults
    if [ "$INTERACTIVE_MODE" = "true" ]; then
        interactive_config "$MODE"
        # MODE might have been changed by interactive_config
        if [ "$DEPLOYMENT_TYPE" = "local_dev" ]; then
            MODE="dev"
        elif [ "$DEPLOYMENT_TYPE" = "local_prod" ] || [ "$DEPLOYMENT_TYPE" = "remote" ]; then
            MODE="production"
        fi
    else
        set_defaults "$MODE"
        print_status "Using default configuration values"
    fi
    
    # Create .env file from scratch if it doesn't exist
    if [ ! -f .env ]; then
        print_status "Creating .env file with configuration..."
        
        # Generate secure credentials
        print_status "Generating secure credentials..."
        SECRET_KEY=$(generate_secret_key)
        DB_PASSWORD=$(openssl rand -base64 32 | tr -d /=+ | cut -c -25)

		# Set DB port comment depending on deployment type
		if [ "$DEPLOYMENT_TYPE" = "local_dev" ]; then
			DB_PORT_COMMENT="# Database port is external only for development"
		else
			DB_PORT_COMMENT="# Database port is internal only for security"
		fi

        # Create .env file directly with all values
        cat > .env << EOF
SECRET_KEY=$SECRET_KEY
POSTGRES_USER=owlculus
POSTGRES_PASSWORD=$DB_PASSWORD
POSTGRES_DB=owlculus
DOMAIN=$CADDY_DOMAIN

# Port Configuration
FRONTEND_PORT=$FRONTEND_PORT
BACKEND_PORT=$BACKEND_PORT
$DB_PORT_COMMENT
DB_PORT=5432

# Reverse Proxy Configuration
USE_REVERSE_PROXY=$USE_REVERSE_PROXY
USE_HTTPS=$USE_HTTPS
EOF
        
        print_success ".env file created with configuration"
    else
        print_status ".env file already exists, using existing configuration"
    fi
    
    # Determine compose files based on deployment type
    if [ "$DEPLOYMENT_TYPE" = "remote" ]; then
        print_status "Starting Owlculus for remote deployment..."
        COMPOSE_TOPOLOGY="$REVERSE_PROXY_TOPOLOGY"
        print_status "Using the shared configuration with the Caddy reverse-proxy overlay"
    elif [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
        print_status "Starting Owlculus in development mode..."
        COMPOSE_TOPOLOGY="$DEV_TOPOLOGY"
    else
        print_status "Starting Owlculus in production mode..."
        COMPOSE_TOPOLOGY="$DIRECT_TOPOLOGY"
    fi
    
    # Build Docker images
    print_status "Building Docker images..."
    if [ "$VERBOSE" = "true" ]; then
        "$DOCKER_COMPOSE_CMD" "$COMPOSE_TOPOLOGY" build
    else
        "$DOCKER_COMPOSE_CMD" "$COMPOSE_TOPOLOGY" build > /dev/null 2>&1
    fi
    
    # Start services
    print_status "Starting services..."
    if [ "$VERBOSE" = "true" ]; then
        "$DOCKER_COMPOSE_CMD" "$COMPOSE_TOPOLOGY" up -d
    else
        "$DOCKER_COMPOSE_CMD" "$COMPOSE_TOPOLOGY" up -d > /dev/null 2>&1
    fi
    
    # Wait for services to be healthy
    print_status "Waiting for services to start..."
    sleep 10
    
    # Check service health
    print_status "Checking service health..."
    sleep 5
    
    # Test services based on deployment type
    if [ "$USE_REVERSE_PROXY" = "true" ]; then
        print_status "Caddy reverse proxy is handling requests"
        print_success "Frontend URL: $FRONTEND_URL"
        print_status "Note: HTTPS certificates will be automatically obtained on first access"
    elif [ "$DEPLOYMENT_TYPE" = "local_dev" ]; then
        # The development backend remains directly reachable for local tooling.
        if curl -f -s "http://$DOMAIN:$BACKEND_PORT/health/ready" > /dev/null; then
            print_success "Development backend is ready"
        else
            print_warning "Development backend may still be starting up"
        fi

        if curl -f -s "$FRONTEND_URL/" > /dev/null; then
            print_success "Frontend is running at $FRONTEND_URL"
        else
            print_warning "Frontend may still be starting up at $FRONTEND_URL"
        fi
    else
        if curl -f -s "$FRONTEND_URL/health/ready" > /dev/null; then
            print_success "Caddy gateway is ready at $FRONTEND_URL"
        else
            print_warning "Caddy gateway may still be starting up at $FRONTEND_URL"
        fi
    fi
    
    # Success message
    echo ""
    print_success "Owlculus setup completed!"
    echo ""
    echo "Owlculus is now running!"
    
    if [ "$DEPLOYMENT_TYPE" = "remote" ]; then
        echo "   URL: https://$DOMAIN"
        echo ""
        echo "Remote Deployment Features:"
        echo "   • Automatic HTTPS with Let's Encrypt certificates"
        echo "   • All services accessible through single endpoint"
        echo "   • Frontend: https://$DOMAIN"
        echo "   • No exposed ports except 80/443"
        echo ""
        print_warning "Important: Ensure DNS for $DOMAIN points to this server!"
    else
        echo "   Frontend: $FRONTEND_URL"
    fi

    echo ""
    # Read the current token from persistent storage, including on setup reruns.
    local SETUP_TOKEN=""
    local SETUP_TOKEN_READ="false"
    local attempt
    for attempt in {1..10}; do
        if SETUP_TOKEN=$("$DOCKER_COMPOSE_CMD" "$COMPOSE_TOPOLOGY" exec -T backend python -c '
import sys
from sqlmodel import Session
from app.core.setup import get_setup_token, is_setup_required
from app.database.connection import engine

with Session(engine) as session:
    if is_setup_required(session):
        token = get_setup_token()
        if not token:
            sys.exit(1)
        print(token)
' 2>/dev/null); then
            SETUP_TOKEN_READ="true"
            break
        fi
        if [ "$attempt" -lt 10 ]; then
            sleep 2
        fi
    done

    if [ "$SETUP_TOKEN_READ" = "true" ] && [ -z "$SETUP_TOKEN" ]; then
        echo "Administrator setup is already complete. Log in at $FRONTEND_URL"
    else
        echo "Complete first-run setup:"
        if [ "$SETUP_TOKEN_READ" = "true" ]; then
            printf '   Setup token: %s\n' "$SETUP_TOKEN"
        else
            print_warning "Could not retrieve the setup token; the backend may still be starting."
            echo "   Retrieve it with: $DOCKER_COMPOSE_CMD $COMPOSE_TOPOLOGY logs backend"
        fi
        echo "   Open $FRONTEND_URL/setup"
        echo "   Enter the token and choose your administrator username and password"
    fi
    
    echo ""
    echo "Useful commands:"
    echo "   Review config:    cat .env"
    echo "   Stop services:    $DOCKER_COMPOSE_CMD $COMPOSE_TOPOLOGY down"
    echo "   View logs:        $DOCKER_COMPOSE_CMD $COMPOSE_TOPOLOGY logs -f"
    echo "   Restart services: $DOCKER_COMPOSE_CMD $COMPOSE_TOPOLOGY restart"
    echo "   Shell access:     $DOCKER_COMPOSE_CMD $COMPOSE_TOPOLOGY exec backend bash"
    echo ""
    
}

# Parse arguments
MODE="production"
VERBOSE="false"
CLEAN="false"

# Parse arguments in order
for arg in "$@"; do
    case "$arg" in
        --verbose)
            VERBOSE="true"
            ;;
        --non-interactive)
            INTERACTIVE_MODE="false"
            ;;
        --clean)
            CLEAN="true"
            ;;
        production|prod|dev|development|help)
            MODE="$arg"
            ;;
    esac
done

# Set default mode if not specified
if [ -z "$MODE" ]; then
    MODE="production"
fi

# Main script logic
case "$MODE" in
    production|prod)
        setup_owlculus "production" "$VERBOSE" "$CLEAN"
        ;;
    development|dev)
        setup_owlculus "dev" "$VERBOSE" "$CLEAN"
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown mode: $MODE"
        echo ""
        show_usage
        exit 1
        ;;
esac
