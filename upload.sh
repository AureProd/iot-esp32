#!/bin/bash

# =====================================================================
# Command Helper / Usage Guide
#
# Purpose:
# Automates the deployment of python code to a microcontroller board.
# It loads environment variables, generates a configuration file from
# a template, cleans the board, and uploads the source files.
#
# Usage:
# ./upload.sh <source_directory> <environment_file> [target_port]
#
# Parameters:
# source_directory : Path to the directory containing the code
# environment_file : Path to the file containing secret variables
# target_port      : Optional parameter for the serial connection
#
# Examples:
#
# Default port deployment:
# ./upload.sh ./led-switch .env.device_1
#
# Custom port deployment:
# ./upload.sh ./led-switch .env.device_2 /dev/ttyUSB_custom
# =====================================================================

# Handle input parameters

# Application folder path parameter
APP_FOLDER=$1
if [ -z "$APP_FOLDER" ]; then
    echo "❌ Error: Please specify the application folder."
    echo "Usage: ./upload.sh <app_folder> <env_file> [port]"
    exit 1
fi

if [ ! -d "$APP_FOLDER" ]; then
    echo "❌ Error: The folder '$APP_FOLDER' does not exist."
    exit 1
fi

# Environment variables file parameter
ENV_FILE=$2
if [ -z "$ENV_FILE" ]; then
    echo "❌ Error: Please specify an environment file."
    echo "Usage: ./upload.sh <app_folder> <env_file> [port]"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: The environment file '$ENV_FILE' does not exist."
    cp ./config/.env.example $ENV_FILE
    echo "📝 The environment file '$ENV_FILE' has been created, please fill it"
    exit 1
fi

# Serial port parameter with a default fallback value
PORT=${3:-"/dev/ttyACM0"}

echo "📂 Source directory: $APP_FOLDER"
echo "🔧 Environment file: $ENV_FILE"
echo "🔌 Target port: $PORT"
echo "-----------------------------------"

# Load environment variables and generate configuration file
echo "⚙️ Loading variables from $ENV_FILE..."
set -a
source "$ENV_FILE"
set +a

# Generate python configuration file from template
TEMPLATE_FILE="$APP_FOLDER/config.py.template"
CONFIG_FILE="$APP_FOLDER/config.py"

if [ -f "$TEMPLATE_FILE" ]; then
    echo "📝 Generating $CONFIG_FILE from template..."
    envsubst < "$TEMPLATE_FILE" > "$CONFIG_FILE"
else
    echo "⚠️ Warning: $TEMPLATE_FILE not found. Skipping generation."
fi

echo "🚀 Connecting to board on port $PORT..."

# Verify tool dependency installation
if ! command -v uv run mpremote &> /dev/null; then
    echo "❌ Error: mpremote is not installed or not in your PATH."
    exit 1
fi

# Wipe existing files from the microcontroller
echo "🧹 Cleaning board (removing old files)..."

CLEAN_PY_SCRIPT="
import os
def clean(path='.'):
    try:
        for f in os.ilistdir(path):
            name = f[0]
            if name in ('.', '..'): continue
            p = path + '/' + name if path != '.' else name
            if f[1] == 0x4000:
                clean(p)
                os.rmdir(p)
            else:
                os.remove(p)
    except Exception as e:
        pass
clean()
"

if ! uv run mpremote connect "$PORT" exec "$CLEAN_PY_SCRIPT"; then
    echo "❌ Error: Failed to access port $PORT during cleanup. It may be in use by another program."
    exit 1
fi
echo "✨ Cleanup finished."

# Transfer files to the microcontroller
echo "📡 Starting upload from $APP_FOLDER..."

for item in "$APP_FOLDER"/*; do
    [ -e "$item" ] || continue
    base_item=$(basename "$item")

    # Skip specific files and directories during upload process
    if [[ "$base_item" == "upload.sh" || "$base_item" == "venv" || "$base_item" == __pycache__* || "$base_item" == .* || "$base_item" == *.template ]]; then
        echo "⏭️ Skipping: $base_item"
        continue
    fi

    if [ -d "$item" ]; then
        echo "📂 Uploading folder: $base_item/"
        if ! uv run mpremote connect "$PORT" fs cp -r "$item" :; then
            echo "❌ Error: Failed to upload folder $base_item. Aborting."
            exit 1
        fi
    elif [ -f "$item" ]; then
        echo "📄 Uploading file: $base_item"
        if ! uv run mpremote connect "$PORT" fs cp "$item" :; then
            echo "❌ Error: Failed to upload file $base_item. Aborting."
            exit 1
        fi
    fi
done

# Restart the microcontroller
echo "🔄 Rebooting board..."
if ! uv run mpremote connect "$PORT" soft-reset; then
    echo "❌ Error: Failed to reboot the board."
    exit 1
fi

echo "✅ Deployment completed successfully!"

# Open interactive session after completion
uv run mpremote connect "$PORT"
