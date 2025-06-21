#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print banner
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════╗"
echo "║        Meeting Transcriber - Development           ║"
echo "╚════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Check if Node modules are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Node modules not found. Installing...${NC}"
    cd frontend
    npm install
    cd ..
fi

# Function to handle script exit
function cleanup {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"

    # Send SIGTERM to all child processes in the backend process group
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${YELLOW}Stopping backend processes...${NC}"
        # Give Python a chance to clean up gracefully
        kill -TERM $BACKEND_PID 2>/dev/null

        # Wait for up to 3 seconds for backend to exit gracefully
        for i in {1..6}; do
            if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
                echo -e "${GREEN}Backend server stopped gracefully.${NC}"
                break
            fi
            sleep 0.5
        done

        # Kill any remaining child processes
        pkill -P $BACKEND_PID 2>/dev/null

        # Force kill if still running
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            echo -e "${RED}Force stopping backend processes...${NC}"
            kill -9 $BACKEND_PID 2>/dev/null
        fi
    fi

    # Kill frontend process
    if [ -n "$FRONTEND_PID" ]; then
        echo -e "${YELLOW}Stopping frontend server...${NC}"
        kill $FRONTEND_PID 2>/dev/null
        sleep 0.5
        # Force kill if still running
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Force stopping frontend server...${NC}"
            kill -9 $FRONTEND_PID 2>/dev/null
        fi
    fi

    echo -e "${GREEN}All processes terminated${NC}"
    # Make sure there are no orphaned Python processes
    if pgrep -f "python.*app.main:app" > /dev/null; then
        echo -e "${YELLOW}Cleaning up orphaned Python processes...${NC}"
        pkill -f "python.*app.main:app"
    fi
    exit 0
}

# Check if backend is running by testing the API endpoint
function check_backend_ready {
    for i in {1..30}; do
        if curl -s http://localhost:8000/api/meetings/ >/dev/null 2>&1; then
            echo -e "${GREEN}Backend API is ready!${NC}"
            return 0
        fi
        echo -e "${YELLOW}Waiting for backend to start (attempt $i/30)...${NC}"
        sleep 1
    done
    echo -e "${RED}Backend failed to start or is not responding.${NC}"
    return 1
}

# Set up trap for clean exit
trap cleanup SIGINT

# Start the backend server
echo -e "${GREEN}Starting backend server...${NC}"
cd backend
go run cmd/backend/main.go &
BACKEND_PID=$!
cd ..

# Wait for backend to initialize and be ready
echo -e "${YELLOW}Waiting for backend API to be available...${NC}"
check_backend_ready

# Start the frontend development server
echo -e "${GREEN}Starting frontend development server...${NC}"
cd frontend
pnpm run dev --open &
FRONTEND_PID=$!
cd ..

echo -e "${GREEN}Both servers are running:${NC}"
echo -e "- ${YELLOW}Frontend:${NC} http://localhost:5173"
echo -e "- ${YELLOW}Backend API:${NC} http://localhost:8000"
echo -e "- ${YELLOW}API Docs:${NC} http://localhost:8000/docs"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"

# Keep the script running
wait $BACKEND_PID $FRONTEND_PID
