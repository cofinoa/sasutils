#!/bin/bash

# Variables
REMOTE_SSH="root@seal"                  # Remote server address
REMOTE_BASE_DIR="/root/deployment"      # Base directory for remote deployment
REMOTE_VENV="${REMOTE_BASE_DIR}/venv"   # Virtual environment directory
REMOTE_APP_DIR="${REMOTE_BASE_DIR}/source" # Application source directory
PYTHON_VERSION="python3"                # Desired Python version (e.g., python3.8)
SSH_CONTROL_PATH="/tmp/test-ssh-%r@%h:%p" # Path for SSH control socket
LOCAL_APP_DIR=".."                      # Local application directory

RSYNC_OPTS="--verbose --archive --delete --prune-empty-dirs --exclude=.git --exclude=.vscode --exclude=__pycache__" # Rsync options

# Function to initialize SSH multiplexed connection
init_connections() {
  ssh -O check -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" &> /dev/null
  if [ $? -eq 0 ]; then
    echo "SSH multiplexed connection already active."
    return
  fi

  echo "Initializing SSH multiplexed connection..."
  ssh -L5678:127.0.0.1:5678 -M -S "${SSH_CONTROL_PATH}" -f -N "${REMOTE_SSH}"
  if [ $? -eq 0 ]; then
    echo "  SSH multiplexed connection initialized successfully."
  else
    echo "  Error: Failed to initialize SSH multiplexed connection."
    exit 1
  fi
}

# Function to set up a virtual environment
setup_venv() {
  init_connections

  ssh -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" "[ -d '${REMOTE_VENV}' ]" &> /dev/null
  if [ $? -eq 0 ]; then
    echo "Virtual environment already exists at ${REMOTE_VENV}. Skipping creation."
    return
  fi

  echo "Setting up virtual environment on remote server..."
  ssh -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^/> /'
    set -e
    mkdir -p "${REMOTE_BASE_DIR}"
    if ! command -v ${PYTHON_VERSION} &> /dev/null; then
      echo "  Error: ${PYTHON_VERSION} is not installed on the remote server."
      exit 1
    fi
    echo "  Creating virtual environment at ${REMOTE_VENV}..."
    ${PYTHON_VERSION} -m venv --upgrade ${REMOTE_VENV}
    echo "  Upgrading pip and setuptools..."
    ${REMOTE_VENV}/bin/pip install --upgrade pip setuptools debugpy
EOF
  echo " Virtual environment setup complete."
}

# Function to deploy the application
deploy_application() {
  setup_venv

  ssh -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" "[ -d '${REMOTE_APP_DIR}' ]" &> /dev/null
  if [ $? -eq 0 ]; then
    echo " Application already deployed at ${REMOTE_APP_DIR}. Updating deployment."
    rsync ${RSYNC_OPTS} "${LOCAL_APP_DIR}" "${REMOTE_SSH}:${REMOTE_APP_DIR}/"
    echo " Updated application deployment successfully."
    return
  fi

  echo " Deploying application to remote server..."
  ssh -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" "mkdir -p ${REMOTE_APP_DIR}"
  rsync ${RSYNC_OPTS} "${LOCAL_APP_DIR}" "${REMOTE_SSH}:${REMOTE_APP_DIR}/"
  if [ $? -eq 0 ]; then
    echo " Application deployed successfully to ${REMOTE_APP_DIR}."
  else
    echo " Error: Failed to deploy application."
    exit 1
  fi
  
  echo " Installing application in editable mode..."
  ssh -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^/> /'
    set -e
    echo " Installing application using pip in editable mode..."
    ${REMOTE_VENV}/bin/pip install --editable ${REMOTE_APP_DIR}
EOF

  echo " Application deployed and installed successfully."
}

# Function to check if debugpy is running
is_debugpy_running() {
  ssh -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF
    set -e
    if [ -f "${REMOTE_BASE_DIR}/debugpy.pid" ]; then
      DEBUGPY_PID=\$(cat ${REMOTE_BASE_DIR}/debugpy.pid)
      if ps -p \$DEBUGPY_PID > /dev/null 2>&1; then
        echo "running \$DEBUGPY_PID"
      else
        echo "stale"
      fi
    else
      echo "not_found"
    fi
EOF
}

# Function to check if debugpy is running
check_debugpy_sessions() {
  echo "Checking for any debugpy sessions running under the remote user..."

  ssh -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^/| /'
    set -e
    DEBUGPY_PROCESSES=\$(ps -u \$(whoami) -o pid,cmd | grep "[d]ebugpy" | awk '{print \$1}')
    if [ -n "\$DEBUGPY_PROCESSES" ]; then
      echo "  Debugpy sessions are running with the following PIDs:"
      echo "\$DEBUGPY_PROCESSES"
    else
      echo "  No debugpy sessions are running under the remote user."
    fi
EOF
}

# Function to stop the debugpy session
stop_debugpy() {
  echo "Stopping all running debugpy sessions on the remote server..."

  ssh -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^/| /'
    set -e
    DEBUGPY_PROCESSES=\$(ps -u \$(whoami) -o pid,cmd | grep "[d]ebugpy" | awk '{print \$1}')
    if [ -n "\$DEBUGPY_PROCESSES" ]; then
      echo "  Found debugpy sessions with the following PIDs:"
      echo "\$DEBUGPY_PROCESSES"
      for PID in \$DEBUGPY_PROCESSES; do
        echo "  Terminating debugpy process with PID: \$PID..."
        kill -9 \$PID
      done
      echo "  All debugpy processes terminated."
      rm -f ${REMOTE_BASE_DIR}/debugpy.pid
    else
      echo "  No debugpy sessions are running under the remote user."
    fi
EOF
}

# Function to launch the application with debugpy
launch_application() {
  if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Error: Missing arguments for launch."
    echo "Usage: $0 launch <debug|run> <entry_point> [optional_args...]"
    exit 1
  fi
 
  MODE="$1" # First argument after "launch" (debug or run)
  ENTRY_POINT="$2" # Second argument after "launch" (entry point)
  shift 2 # Remove "launch", mode, and entry point from the arguments

  OPTIONAL_ARGS="$@" # Capture all remaining arguments as optional arguments

  deploy_application

  case "$MODE" in
    "debug")
       echo " Checking if debugpy is already running..."
       DEBUGPY_STATUS=$(is_debugpy_running | tail -n 1)
             if [[ "$DEBUGPY_STATUS" == running* ]]; then
         echo " Debugpy is already running with PID: ${DEBUGPY_STATUS#running }"
         echo " Please stop the existing debugpy session before launching a new one."
         exit 1
       fi
  
       echo " Debugging application with debugpy on remote server..."
       ssh -L5678:127.0.0.1:5678 -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^//'
         set -e
         echo " Starting application with debugpy..."
         ${REMOTE_VENV}/bin/python -m debugpy --listen 127.0.0.1:5678 --wait-for-client ${REMOTE_APP_DIR}/${ENTRY_POINT} ${OPTIONAL_ARGS}
EOF
      ;;
    "run")
       echo " Running application on remote server..."
       ssh -L5678:127.0.0.1:5678 -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^//'
         set -e
         ${REMOTE_VENV}/bin/python ${REMOTE_APP_DIR}/${ENTRY_POINT} ${OPTIONAL_ARGS}
EOF
      ;;
    *)
      echo "Error: Invalid mode '$MODE'. Use 'debug' or 'run'."
      echo "Usage: $0 <debug|run> <entry_point> [optional_args...]"
      exit 1
      ;;
  esac

}

# Function to check the status of the deployment
check_status() {
  echo " Checking deployment status..."

  # Check SSH connection
  ssh -O check -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" &> /dev/null
  if [ $? -eq 0 ]; then
    echo " SSH multiplexed connection: ACTIVE"
  else
    echo " SSH multiplexed connection: INACTIVE"
  fi

  # Check virtual environment
  ssh -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" "[ -d '${REMOTE_VENV}' ]" &> /dev/null
  if [ $? -eq 0 ]; then
    echo " Virtual environment: EXISTS at ${REMOTE_VENV}"
  else
    echo " Virtual environment: NOT FOUND"
  fi

  # Check application deployment
  ssh -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" "[ -d '${REMOTE_APP_DIR}' ]" &> /dev/null
  if [ $? -eq 0 ]; then
    echo " Application deployment: EXISTS at ${REMOTE_APP_DIR}"
  else
    echo " Application deployment: NOT FOUND"
  fi

  # Check if debugpy is running
  echo " Checking debugpy status..."
  DEBUGPY_STATUS=$(is_debugpy_running | tail -n 1)
  if [[ "$DEBUGPY_STATUS" == running* ]]; then
    echo "Debugpy is running with PID: ${DEBUGPY_STATUS#running }"
  elif [[ "$DEBUGPY_STATUS" == "stale" ]]; then
    echo " Debugpy PID file exists, but process is not running."
  else
    echo " Debugpy is not running (no PID file found)."
  fi
}

# Function to destroy the deployment
destroy() {
  echo "Destroying remote deployment and stopping SSH connection..."

  # Ensure SSH connection is initialized
  init_connections

  # Check and terminate any running debugpy processes
  stop_debugpy
  
  # Remove the remote base directory
  echo " Removing remote base directory..."
  ssh -T -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" << EOF | sed 's/^/> /'
    set -e
    if [ -d "${REMOTE_BASE_DIR}" ]; then
      echo " Removing remote base directory: ${REMOTE_BASE_DIR}"
      rm -rf "${REMOTE_BASE_DIR}"
    else
      echo " Remote base directory does not exist: ${REMOTE_BASE_DIR}"
    fi
EOF

  # Stop the SSH multiplexed connection
  ssh -O exit -S "${SSH_CONTROL_PATH}" "${REMOTE_SSH}" &> /dev/null
  if [ $? -eq 0 ]; then
    echo " SSH multiplexed connection stopped successfully."
  else
    echo " Error: Failed to stop SSH multiplexed connection or no connection exists."
  fi

  echo " Remote deployment destroyed successfully."
}

# Main script logic
case "$1" in
  "init")
    init_connections
    ;;
  "setup")
    setup_venv
    ;;
  "deploy")
    deploy_application
    ;;
  "debug")
    launch_application "$@"
    ;;
  "run")
    launch_application "$@"
    ;;
  "stop")
    stop_debugpy
    ;;
  "destroy")
    destroy
    ;;
  "status")
    check_status
    ;;
  "status-debugpy")
    is_debugpy_running
    ;;
  "check-sessions")
    check_debugpy_sessions
    ;;
  *)
    echo "Usage: $0 {init|setup|deploy|stop|destroy|status|status-debugpy|check-sessions|<debug|run> <entry_point> [optional_args...]}"
    exit 1
    ;;
esac