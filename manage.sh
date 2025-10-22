#!/bin/bash

# Blockchain Project Management Script
# Single entry point for all blockchain project operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_help() {
    echo -e "${BLUE}NIL Blockchain Project Management${NC}"
    echo "================================="
    echo ""
    echo "Usage: ./manage.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  setup           - Set up development environment"
    echo "  start           - Start development services"
    echo "  stop            - Stop development services" 
    echo "  test            - Run tests"
    echo "  deploy <env>    - Deploy to environment (development/production)"
    echo "  clean           - Clean up all resources"
    echo "  status          - Show service status"
    echo "  logs [service]  - Show logs"
    echo "  shell [service] - Access service shell"
    echo ""
    echo "Examples:"
    echo "  ./manage.sh setup"
    echo "  ./manage.sh start"
    echo "  ./manage.sh test"
    echo "  ./manage.sh deploy development"
    echo "  ./manage.sh logs blockchain-service"
}

setup_environment() {
    echo -e "${YELLOW}[INFO]${NC} Setting up development environment..."
    
    # Create virtual environment if not exists
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo -e "${GREEN}[SUCCESS]${NC} Created virtual environment"
    fi
    
    # Activate and install dependencies
    source venv/bin/activate
    pip install -r lambda/requirements.txt
    echo -e "${GREEN}[SUCCESS]${NC} Installed Python dependencies"
    
    # Copy environment configuration
    if [ ! -f ".env" ]; then
        cp config/development.env .env
        echo -e "${GREEN}[SUCCESS]${NC} Created .env file"
    fi
    
    echo -e "${GREEN}[SUCCESS]${NC} Development environment ready"
}

start_services() {
    echo -e "${YELLOW}[INFO]${NC} Starting blockchain services..."
    docker-compose up -d --build
    echo -e "${GREEN}[SUCCESS]${NC} Services started"
    echo ""
    echo "Access points:"
    echo "  • Blockchain API: http://localhost:8002"
    echo "  • Database Admin: http://localhost:8081"
    echo "  • API Documentation: http://localhost:8002/docs"
}

stop_services() {
    echo -e "${YELLOW}[INFO]${NC} Stopping blockchain services..."
    docker-compose down
    echo -e "${GREEN}[SUCCESS]${NC} Services stopped"
}

run_tests() {
    echo -e "${YELLOW}[INFO]${NC} Running blockchain tests..."
    
    if [ -f "tests/test_docker_setup.sh" ]; then
        chmod +x tests/test_docker_setup.sh
        ./tests/test_docker_setup.sh
    else
        echo -e "${RED}[ERROR]${NC} Test script not found"
        exit 1
    fi
}

deploy_environment() {
    local environment=${1:-"development"}
    echo -e "${YELLOW}[INFO]${NC} Deploying to $environment..."
    
    if [ -f "scripts/deploy-consolidated.sh" ]; then
        chmod +x scripts/deploy-consolidated.sh
        ./scripts/deploy-consolidated.sh "$environment"
    else
        echo -e "${RED}[ERROR]${NC} Deployment script not found"
        exit 1
    fi
}

clean_resources() {
    echo -e "${YELLOW}[INFO]${NC} Cleaning up resources..."
    docker-compose down -v
    docker system prune -f
    echo -e "${GREEN}[SUCCESS]${NC} Cleanup completed"
}

show_status() {
    echo -e "${BLUE}Blockchain Service Status${NC}"
    echo "========================="
    docker-compose ps
}

show_logs() {
    local service=${1:-""}
    if [ -n "$service" ]; then
        docker-compose logs -f "$service"
    else
        docker-compose logs -f
    fi
}

access_shell() {
    local service=${1:-"blockchain-service"}
    docker-compose exec "$service" /bin/bash
}

# Main command handling
case ${1:-""} in
    "setup")
        setup_environment
        ;;
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    "test")
        run_tests
        ;;
    "deploy")
        deploy_environment "$2"
        ;;
    "clean")
        clean_resources
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$2"
        ;;
    "shell")
        access_shell "$2"
        ;;
    "help"|"--help"|"-h")
        print_help
        ;;
    "")
        print_help
        ;;
    *)
        echo -e "${RED}[ERROR]${NC} Unknown command: $1"
        echo ""
        print_help
        exit 1
        ;;
esac
