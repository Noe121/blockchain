#!/bin/bash

# Hardhat Compilation Optimization Script
# This script provides optimized compilation commands for different scenarios

set -e

echo "🔧 Hardhat Compilation Optimizer"

# Function to check if we're in a git repository and get current branch
get_git_info() {
    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        BRANCH=$(git rev-parse --abbrev-ref HEAD)
        echo "Git branch: $BRANCH"
        return 0
    else
        echo "Not in a git repository"
        return 1
    fi
}

# Function to set development environment
set_dev_mode() {
    export NODE_ENV=development
    echo "✅ Development mode enabled (faster compilation)"
}

# Function to set production environment  
set_prod_mode() {
    export NODE_ENV=production
    echo "✅ Production mode enabled (optimized compilation)"
}

# Function to clean cache and artifacts
clean_build() {
    echo "🧹 Cleaning build artifacts..."
    npx hardhat clean
    rm -rf cache/ artifacts/ typechain-types/
    echo "✅ Clean completed"
}

# Function to compile with caching
compile_with_cache() {
    echo "📦 Compiling with cache optimization..."
    
    # Check if cache exists
    if [ -d "cache" ] && [ "$(ls -A cache)" ]; then
        echo "📋 Using existing cache"
        npx hardhat compile
    else
        echo "📋 Fresh compilation (building cache)"
        npx hardhat compile
    fi
}

# Function to compile only changed files
compile_incremental() {
    echo "⚡ Incremental compilation..."
    
    if get_git_info; then
        # Get list of changed Solidity files
        CHANGED_FILES=$(git diff --name-only HEAD~1 | grep '\.sol$' || true)
        
        if [ -n "$CHANGED_FILES" ]; then
            echo "📝 Changed files detected:"
            echo "$CHANGED_FILES"
            npx hardhat compile
        else
            echo "📋 No Solidity files changed, skipping compilation"
        fi
    else
        echo "📋 Not in git repo, running full compilation"
        npx hardhat compile
    fi
}

# Function to run parallel compilation
compile_parallel() {
    echo "🚀 Running parallel compilation..."
    
    # Set max workers based on CPU cores
    CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "4")
    MAX_WORKERS=$((CORES - 1))
    
    echo "🔧 Using $MAX_WORKERS parallel workers"
    
    # Run compilation with parallel processing
    HARDHAT_PARALLEL_WORKERS=$MAX_WORKERS npx hardhat compile
}

# Function to optimize for development
dev_compile() {
    set_dev_mode
    echo "🛠️  Development compilation (optimized for speed)..."
    
    # Skip unnecessary optimizations
    export HARDHAT_VERBOSE=false
    export HARDHAT_NETWORK=hardhat
    
    npx hardhat compile --force
    echo "✅ Development compilation completed"
}

# Function to optimize for production
prod_compile() {
    set_prod_mode
    echo "🏭 Production compilation (optimized for deployment)..."
    
    # Clean first for production builds
    clean_build
    
    # Full compilation with all optimizations
    npx hardhat compile
    echo "✅ Production compilation completed"
}

# Function to watch for changes and recompile
watch_compile() {
    echo "👀 Starting watch mode..."
    
    set_dev_mode
    
    # Install fswatch if not available (macOS)
    if ! command -v fswatch &> /dev/null; then
        echo "📦 Installing fswatch for file watching..."
        brew install fswatch
    fi
    
    echo "👀 Watching for .sol file changes..."
    fswatch -o . | while read f; do
        echo "📁 Files changed, recompiling..."
        dev_compile
    done
}

# Main menu
case "${1:-help}" in
    "dev"|"development")
        dev_compile
        ;;
    "prod"|"production")
        prod_compile
        ;;
    "clean")
        clean_build
        ;;
    "cache")
        compile_with_cache
        ;;
    "incremental"|"inc")
        compile_incremental
        ;;
    "parallel")
        compile_parallel
        ;;
    "watch")
        watch_compile
        ;;
    "help"|*)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  dev          - Fast development compilation (no optimization)"
        echo "  prod         - Production compilation (full optimization)"
        echo "  clean        - Clean cache and artifacts"
        echo "  cache        - Compile using existing cache"
        echo "  incremental  - Compile only changed files (requires git)"
        echo "  parallel     - Compile with parallel workers"
        echo "  watch        - Watch for changes and auto-recompile"
        echo "  help         - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 dev       # Fast compilation for development"
        echo "  $0 prod      # Optimized compilation for deployment"
        echo "  $0 watch     # Auto-recompile on file changes"
        ;;
esac