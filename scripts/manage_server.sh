#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# PID file locations
PID_FILE="/tmp/pos_server.pid"
# DOC_PID_FILE="/tmp/pos_docs.pid"  # Commented out as we're not using the separate docs server

# Function to check if a process is running
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null; then
            return 0
        fi
    fi
    return 1
}

# Function to setup virtual environment if it doesn't exist
setup_venv() {
    if [ ! -d "venv" ]; then
        echo "Setting up virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi
}

# Function to report status
status() {
    if is_running "$PID_FILE"; then
        echo -e "${GREEN}Backend server is running (PID: $(cat $PID_FILE))${NC}"
        echo -e "${GREEN}API Documentation available at:${NC}"
        echo -e "  - Swagger UI: http://localhost:8000/docs"
        echo -e "  - ReDoc: http://localhost:8000/redoc"
    else
        echo -e "${RED}Backend server is not running${NC}"
    fi

    # Commented out separate documentation server status
    # if is_running "$DOC_PID_FILE"; then
    #     echo -e "${GREEN}Documentation server is running (PID: $(cat $DOC_PID_FILE))${NC}"
    # else
    #     echo -e "${RED}Documentation server is not running${NC}"
    # fi
}

# Function to start servers
start() {
    echo "Starting backend server..."
    setup_venv

    if is_running "$PID_FILE"; then
        echo -e "${YELLOW}Backend server is already running${NC}"
    else
        python app.py &
        echo $! > "$PID_FILE"
        echo -e "${GREEN}Backend server started${NC}"
    fi

    # Commented out separate documentation server start
    # if is_running "$DOC_PID_FILE"; then
    #     echo -e "${YELLOW}Documentation server is already running${NC}"
    # else
    #     python docs_server.py &
    #     echo $! > "$DOC_PID_FILE"
    #     echo -e "${GREEN}Documentation server started${NC}"
    # fi

    sleep 2
    status
}

# Function to stop servers
stop() {
    if is_running "$PID_FILE"; then
        kill $(cat "$PID_FILE")
        rm "$PID_FILE"
        echo -e "${GREEN}Backend server stopped${NC}"
    else
        echo -e "${YELLOW}Backend server is not running${NC}"
    fi

    # Commented out separate documentation server stop
    # if is_running "$DOC_PID_FILE"; then
    #     kill $(cat "$DOC_PID_FILE")
    #     rm "$DOC_PID_FILE"
    #     echo -e "${GREEN}Documentation server stopped${NC}"
    # else
    #     echo -e "${YELLOW}Documentation server is not running${NC}"
    # fi
}

# Function to restart servers
restart() {
    echo "Restarting backend server..."
    stop
    sleep 2
    start
}

# Main script
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0 