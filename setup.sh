#!/bin/bash

# Owlculus Docker Setup Script
# Interactive setup with customizable defaults

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

# Default configuration values
DEFAULT_FRONTEND_PORT=80
DEFAULT_BACKEND_PORT=8000
DEFAULT_DB_PORT=5432
DEFAULT_DOMAIN="localhost"
DEFAULT_ADMIN_USERNAME="admin"
DEFAULT_ADMIN_EMAIL="admin@example.com"

# Configuration variables
FRONTEND_PORT=""
BACKEND_PORT=""
DB_PORT=""
DOMAIN=""
ADMIN_USERNAME=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
INTERACTIVE_MODE="true"

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

# Function to run interactive configuration
interactive_config() {
    local MODE="$1"
    echo ""
    echo "Owlculus Interactive Setup"
    echo "=========================="
    echo ""
    echo "Configure your Owlculus installation. Press Enter to use defaults."
    echo ""
    
    # Adjust default frontend port for dev mode
    local DEFAULT_FE_PORT="$DEFAULT_FRONTEND_PORT"
    if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
        DEFAULT_FE_PORT="5173"
    fi
    
    # Network Configuration
    echo "Network Configuration:"
    echo "---------------------"
    
    while true; do
        DOMAIN=$(prompt_with_default "Domain/Hostname (without port or protocol)" "$DEFAULT_DOMAIN")
        if [ -n "$DOMAIN" ]; then
            break
        fi
        print_error "Domain/Hostname cannot be empty"
    done
    
    while true; do
        FRONTEND_PORT=$(prompt_with_default "Frontend port" "$DEFAULT_FE_PORT")
        if validate_port "$FRONTEND_PORT"; then
            break
        fi
        print_error "Invalid port number. Please enter a number between 1-65535"
    done
    
    while true; do
        BACKEND_PORT=$(prompt_with_default "Backend API port" "$DEFAULT_BACKEND_PORT")
        if validate_port "$BACKEND_PORT"; then
            break
        fi
        print_error "Invalid port number. Please enter a number between 1-65535"
    done
    
    while true; do
        DB_PORT=$(prompt_with_default "Database port" "$DEFAULT_DB_PORT")
        if validate_port "$DB_PORT"; then
            break
        fi
        print_error "Invalid port number. Please enter a number between 1-65535"
    done
    
    echo ""
    echo "Admin Account Configuration:"
    echo "---------------------------"
    
    while true; do
        ADMIN_USERNAME=$(prompt_with_default "Admin username" "$DEFAULT_ADMIN_USERNAME")
        if [ -n "$ADMIN_USERNAME" ]; then
            break
        fi
        print_error "Username cannot be empty"
    done
    
    while true; do
        ADMIN_EMAIL=$(prompt_with_default "Admin email" "$DEFAULT_ADMIN_EMAIL")
        if [[ "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
            break
        fi
        print_error "Please enter a valid email address"
    done
    
    echo ""
    echo -n "Admin password (leave empty for auto-generated): "
    read -s ADMIN_PASSWORD
    echo ""
    
    if [ -z "$ADMIN_PASSWORD" ]; then
        ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d /=+ | cut -c -12)
        print_status "Auto-generated secure admin password"
    fi
    
    # Construct URLs from domain and ports
    FRONTEND_URL="http://$DOMAIN:$FRONTEND_PORT"
    BACKEND_API_URL="http://$DOMAIN:$BACKEND_PORT"
    
    # Clean up URLs if using standard ports
    if [ "$FRONTEND_PORT" = "80" ]; then
        FRONTEND_URL="http://$DOMAIN"
    fi
    
    echo ""
    echo "Configuration Summary:"
    echo "====================="
    echo "Domain: $DOMAIN"
    echo "Frontend URL: $FRONTEND_URL"
    echo "Backend API URL: $BACKEND_API_URL"
    echo "Frontend Port: $FRONTEND_PORT"
    echo "Backend Port: $BACKEND_PORT"
    echo "Database Port: $DB_PORT"
    echo "Admin Username: $ADMIN_USERNAME"
    echo "Admin Email: $ADMIN_EMAIL"
    echo "Admin Password: [set]"
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
    echo "Examples:"
    echo "  $0                          # Interactive production setup"
    echo "  $0 dev                      # Interactive development setup"
    echo "  $0 --non-interactive        # Non-interactive production setup"
    echo "  $0 dev --verbose            # Development setup with full Docker output"
    echo "  $0 --clean                  # Clean setup (removes Owlculus Docker artifacts)"
    echo "  $0 dev --clean --verbose    # Clean dev setup with verbose output"
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
    if docker compose -f docker-compose.yml ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping production containers..."
        docker compose -f docker-compose.yml down 2>/dev/null || true
    fi
    
    if docker compose -f docker-compose.dev.yml ps -q 2>/dev/null | grep -q .; then
        print_status "Stopping development containers..."
        docker compose -f docker-compose.dev.yml down 2>/dev/null || true
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
    local DEFAULT_FE_PORT="$DEFAULT_FRONTEND_PORT"
    
    # Adjust default frontend port for dev mode
    if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
        DEFAULT_FE_PORT="5173"
    fi
    
    DOMAIN="$DEFAULT_DOMAIN"
    FRONTEND_PORT="$DEFAULT_FE_PORT"
    BACKEND_PORT="$DEFAULT_BACKEND_PORT"
    DB_PORT="$DEFAULT_DB_PORT"
    
    # Construct URLs
    BACKEND_API_URL="http://$DOMAIN:$BACKEND_PORT"
    FRONTEND_URL="http://$DOMAIN:$FRONTEND_PORT"
    
    # Clean up frontend URL if using standard port
    if [ "$FRONTEND_PORT" = "80" ]; then
        FRONTEND_URL="http://$DOMAIN"
    fi
    
    ADMIN_USERNAME="$DEFAULT_ADMIN_USERNAME"
    ADMIN_EMAIL="$DEFAULT_ADMIN_EMAIL"
    ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d /=+ | cut -c -12)
}

# Main setup function
setup_owlculus() {
    local MODE="${1:-production}"
    local VERBOSE="${2:-false}"
    local CLEAN="${3:-false}"
    local ADMIN_PASSWORD_TO_DISPLAY=""
    
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
    if ! docker compose version >/dev/null 2>&1 && ! command_exists docker-compose; then
        print_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    # Use docker compose if available, fallback to docker-compose
    if docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
    
    print_status "Docker and Docker Compose are available"
    
    # Run interactive configuration or use defaults
    if [ "$INTERACTIVE_MODE" = "true" ]; then
        interactive_config "$MODE"
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
        
        # Create .env file directly with all values
        cat > .env << EOF
SECRET_KEY=$SECRET_KEY
POSTGRES_USER=owlculus
POSTGRES_PASSWORD=$DB_PASSWORD
POSTGRES_DB=owlculus
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD
ADMIN_EMAIL=$ADMIN_EMAIL

# Port Configuration
FRONTEND_PORT=$FRONTEND_PORT
BACKEND_PORT=$BACKEND_PORT
DB_PORT=$DB_PORT

# URL Configuration
FRONTEND_URL=$FRONTEND_URL
BACKEND_URL=$BACKEND_API_URL
EOF
        
        print_success ".env file created with configuration"
        ADMIN_PASSWORD_TO_DISPLAY="$ADMIN_PASSWORD"
    else
        print_status ".env file already exists, using existing configuration"
    fi
    
    # Create frontend .env file with API URL
    print_status "Creating frontend environment configuration..."
    
    cat > frontend/.env << EOF
VITE_API_BASE_URL=$BACKEND_API_URL
EOF
    
    print_success "Frontend configuration created with API URL: $BACKEND_API_URL"
    
    # Determine compose file based on mode
    if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
        print_status "Starting Owlculus in development mode..."
        COMPOSE_FILE="docker-compose.dev.yml"
    else
        print_status "Starting Owlculus in production mode..."
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # Build Docker images
    print_status "Building Docker images..."
    if [ "$VERBOSE" = "true" ]; then
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE build
    else
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE build > /dev/null 2>&1
    fi
    
    # Start services
    print_status "Starting services..."
    if [ "$VERBOSE" = "true" ]; then
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE up -d
    else
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE up -d > /dev/null 2>&1
    fi
    
    # Wait for services to be healthy
    print_status "Waiting for services to start..."
    sleep 10
    
    # Check service health
    print_status "Checking service health..."
    sleep 5
    
    # Test backend
    if curl -f -s "$BACKEND_API_URL/" > /dev/null; then
        print_success "Backend is running at $BACKEND_API_URL"
    else
        print_warning "Backend may still be starting up at $BACKEND_API_URL"
    fi
    
    # Test frontend
    if curl -f -s "$FRONTEND_URL/" > /dev/null; then
        print_success "Frontend is running at $FRONTEND_URL"
    else
        print_warning "Frontend may still be starting up at $FRONTEND_URL"
    fi
    
    # Success message
    echo ""
    print_success "Owlculus setup completed!"
    echo ""
    echo "Owlculus is now running!"
    echo "   Frontend: $FRONTEND_URL"
    echo "   Backend API: $BACKEND_API_URL"
    echo ""
    echo "Useful commands:"
    echo "   Show credentials: cat .env"
    echo "   Stop services:    $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE down"
    echo "   View logs:        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE logs -f"
    echo "   Restart services: $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE restart"
    echo "   Shell access:     $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE exec backend bash"
    echo ""
    
    # Display admin credentials at the very end if they were generated
    if [ -n "$ADMIN_PASSWORD_TO_DISPLAY" ]; then
        echo "Generated admin credentials:"
        echo "   Username: $ADMIN_USERNAME"
        echo "   Password: $ADMIN_PASSWORD_TO_DISPLAY"
        echo ""
        print_warning "Save the admin password above - you'll need it to log in!"
        echo ""
    fi
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