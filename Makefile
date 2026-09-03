# Owlculus Docker Management
.PHONY: help setup setup-dev start start-dev stop restart logs clean build rebuild test test-browser

COMPOSE = ./scripts/compose.sh direct
DEV_COMPOSE = ./scripts/compose.sh development

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
	@echo "  test-browser - Run the first-install browser journey against ephemeral stacks"
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
	$(COMPOSE) up -d

start-dev:
	@echo "▶️  Starting Owlculus (development)..."
	$(DEV_COMPOSE) up -d

stop:
	@echo "⏹️  Stopping Owlculus..."
	$(COMPOSE) down
	$(DEV_COMPOSE) down

restart:
	@echo "🔄 Restarting Owlculus..."
	$(COMPOSE) restart
	$(DEV_COMPOSE) restart

# Monitoring
logs:
	@echo "📋 Viewing service logs (Ctrl+C to exit)..."
	$(COMPOSE) logs -f

# Build commands
build:
	@echo "🔨 Building Docker images..."
	$(COMPOSE) build

rebuild:
	@echo "🔨 Rebuilding Docker images (no cache)..."
	$(COMPOSE) build --no-cache
	$(DEV_COMPOSE) build --no-cache

# Cleanup
clean:
	@echo "🧹 Cleaning up all Docker resources..."
	@echo "⚠️  This will destroy all data! Press Ctrl+C to cancel..."
	@sleep 5
	$(COMPOSE) down -v --remove-orphans
	$(DEV_COMPOSE) down -v --remove-orphans
	docker system prune -f

# Testing
test:
	@echo "🧪 Running backend tests..."
	$(COMPOSE) exec backend python3 -m pytest tests/ -v

test-browser:
	@echo "🧪 Running first-install browser journey..."
	cd frontend && npm run test:e2e

# Development helpers
shell-backend:
	@echo "🐚 Opening backend shell..."
	$(COMPOSE) exec backend bash

shell-db:
	@echo "🐚 Opening database shell..."
	$(COMPOSE) exec postgres psql -U owlculus -d owlculus

# Status
status:
	@echo "📊 Service Status:"
	$(COMPOSE) ps
