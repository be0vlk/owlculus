# Owlculus Docker Management
.PHONY: help setup setup-dev start start-dev stop restart logs clean build rebuild test

# Default target
help:
	@echo "🦉 Owlculus Docker Management"
	@echo ""
	@echo "Available commands:"
	@echo "  setup       - Initial setup with Docker (production)"
	@echo "  setup-dev   - Initial setup with Docker (development)"
	@echo "  start       - Start all services (production)"
	@echo "  start-dev   - Start all services (development)"
	@echo "  stop        - Stop all services"
	@echo "  restart     - Restart all services"
	@echo "  logs        - View service logs"
	@echo "  build       - Build Docker images"
	@echo "  rebuild     - Rebuild Docker images (no cache)"
	@echo "  clean       - Stop and remove all containers, networks, and volumes"
	@echo "  test        - Run backend tests"
	@echo ""

# Setup commands
setup:
	@echo "🚀 Setting up Owlculus (production)..."
	./setup.sh docker

setup-dev:
	@echo "🚀 Setting up Owlculus (development)..."
	./setup.sh docker dev

# Service management
start:
	@echo "▶️  Starting Owlculus (production)..."
	docker compose up -d

start-dev:
	@echo "▶️  Starting Owlculus (development)..."
	docker compose -f docker-compose.dev.yml up -d

stop:
	@echo "⏹️  Stopping Owlculus..."
	docker compose down
	docker compose -f docker-compose.dev.yml down

restart:
	@echo "🔄 Restarting Owlculus..."
	docker compose restart
	docker compose -f docker-compose.dev.yml restart

# Monitoring
logs:
	@echo "📋 Viewing service logs (Ctrl+C to exit)..."
	docker compose logs -f

# Build commands
build:
	@echo "🔨 Building Docker images..."
	docker compose build

rebuild:
	@echo "🔨 Rebuilding Docker images (no cache)..."
	docker compose build --no-cache
	docker compose -f docker-compose.dev.yml build --no-cache

# Cleanup
clean:
	@echo "🧹 Cleaning up all Docker resources..."
	@echo "⚠️  This will destroy all data! Press Ctrl+C to cancel..."
	@sleep 5
	docker compose down -v --remove-orphans
	docker compose -f docker-compose.dev.yml down -v --remove-orphans
	docker system prune -f

# Testing
test:
	@echo "🧪 Running backend tests..."
	docker compose exec backend python3 -m pytest tests/ -v

# Development helpers
shell-backend:
	@echo "🐚 Opening backend shell..."
	docker compose exec backend bash

shell-db:
	@echo "🐚 Opening database shell..."
	docker compose exec postgres psql -U owlculus -d owlculus

# Status
status:
	@echo "📊 Service Status:"
	docker compose ps