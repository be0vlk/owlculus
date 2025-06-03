#!/bin/bash

# Owlculus Docker Setup Script
# Simplified Docker-only setup for consistent environments

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

# Function to show usage
show_usage() {
    echo "🦉 Owlculus Docker Setup"
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
    echo
    echo "Examples:"
    echo "  $0                    # Production setup (quiet mode)"
    echo "  $0 dev                # Development setup (quiet mode)"
    echo "  $0 production --verbose # Production setup with full Docker output"
    echo
    echo "Requirements:"
    echo "  - Docker"
    echo "  - Docker Compose"
    echo
}

# Main setup function
setup_owlculus() {
    local MODE="${1:-production}"
    local VERBOSE="${2:-false}"
    local ADMIN_PASSWORD_TO_DISPLAY=""
    
    print_status "🦉 Setting up Owlculus with Docker..."
    
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
    
    print_status "✅ Docker and Docker Compose are available"
    
    # Create .env file from template if it doesn't exist
    if [ ! -f .env ]; then
        print_status "📝 Creating .env file from template..."
        cp .env.example .env
        
        # Generate secure credentials
        print_status "🔐 Generating secure credentials..."
        SECRET_KEY=$(generate_secret_key)
        DB_PASSWORD=$(openssl rand -base64 32 | tr -d /=+ | cut -c -25)
        ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d /=+ | cut -c -12)
        
        # Replace placeholders
        sed -i.bak "s/generate-a-secure-key-with-at-least-32-characters/$SECRET_KEY/" .env
        sed -i.bak "s/your-secure-database-password/$DB_PASSWORD/" .env  
        sed -i.bak "s/your-secure-admin-password/$ADMIN_PASSWORD/" .env
        rm -f .env.bak
        
        print_success "✅ .env file created with generated credentials"
        ADMIN_PASSWORD_TO_DISPLAY="$ADMIN_PASSWORD"
    else
        print_status "📄 .env file already exists, using existing configuration"
    fi
    
    # Determine compose file based on mode
    if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
        print_status "🚀 Starting Owlculus in development mode..."
        COMPOSE_FILE="docker-compose.dev.yml"
        FRONTEND_URL="http://localhost:5173"
    else
        print_status "🚀 Starting Owlculus in production mode..."
        COMPOSE_FILE="docker-compose.yml"
        FRONTEND_URL="http://localhost"
    fi
    
    BACKEND_URL="http://localhost:8000"
    
    # Build Docker images
    print_status "🔨 Building Docker images..."
    if [ "$VERBOSE" = "true" ]; then
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE build
    else
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE build > /dev/null 2>&1
    fi
    
    # Start services
    print_status "🐳 Starting services..."
    if [ "$VERBOSE" = "true" ]; then
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE up -d
    else
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE up -d > /dev/null 2>&1
    fi
    
    # Wait for services to be healthy
    print_status "⏳ Waiting for services to start..."
    sleep 10
    
    # Check service health
    print_status "🏥 Checking service health..."
    sleep 5
    
    # Test backend
    if curl -f -s "$BACKEND_URL/" > /dev/null; then
        print_success "✅ Backend is running at $BACKEND_URL"
    else
        print_warning "⚠️  Backend may still be starting up at $BACKEND_URL"
    fi
    
    # Test frontend
    if curl -f -s "$FRONTEND_URL/" > /dev/null; then
        print_success "✅ Frontend is running at $FRONTEND_URL"
    else
        print_warning "⚠️  Frontend may still be starting up at $FRONTEND_URL"
    fi
    
    # Success message
    echo ""
    print_success "🎉 Owlculus setup completed!"
    echo ""
    echo "🦉 Owlculus is now running!"
    echo "   🌐 Frontend: $FRONTEND_URL"
    echo "   🔧 Backend API: $BACKEND_URL"
    echo ""
    echo "📋 Useful commands:"
    echo "   Show credentials: cat .env"
    echo "   Stop services:    $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE down"
    echo "   View logs:        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE logs -f"
    echo "   Restart services: $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE restart"
    echo "   Shell access:     $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE exec backend bash"
    echo ""
    
    # Display admin credentials at the very end if they were generated
    if [ -n "$ADMIN_PASSWORD_TO_DISPLAY" ]; then
        echo "🔐 Generated admin credentials:"
        echo "   Username: admin"
        echo "   Password: $ADMIN_PASSWORD_TO_DISPLAY"
        echo ""
        print_warning "💾 Save the admin password above - you'll need it to log in!"
        echo ""
    fi
}

# Parse arguments
MODE="${1:-production}"
VERBOSE="false"

# Check for verbose flag in any argument position
for arg in "$@"; do
    if [ "$arg" = "--verbose" ]; then
        VERBOSE="true"
        break
    fi
done

# Main script logic
case "$MODE" in
    production|prod)
        setup_owlculus "production" "$VERBOSE"
        ;;
    development|dev)
        setup_owlculus "dev" "$VERBOSE"
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