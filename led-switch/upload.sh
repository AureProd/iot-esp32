#!/bin/bash

APP_FOLDER="./led-switch/src"

# Default port.
# PORT="/dev/ttyUSB0"
PORT="/dev/ttyACM0"

echo "🚀 Connecting to ESP32 on port $PORT..."

# 1. Check for mpremote
if ! command -v uv run mpremote &> /dev/null; then
    echo "❌ Error: 'mpremote' is not installed or not in your PATH."
    echo "Please install it by running: pip install mpremote"
    exit 1
fi

# 2. Complete cleanup of the ESP32 (Wipe)
echo "🧹 Cleaning ESP32 (removing old files)..."

# This Python snippet runs directly on the ESP32 to clear its filesystem
CLEAN_PY_SCRIPT="
import os
def clean(path='.'):
    try:
        for f in os.ilistdir(path):
            name = f[0]
            if name in ('.', '..'): continue
            p = path + '/' + name if path != '.' else name
            if f[1] == 0x4000: # If it is a directory
                clean(p)
                os.rmdir(p)
            else: # If it is a file
                os.remove(p)
    except Exception as e:
        pass
clean()
"
uv run mpremote connect $PORT exec "$CLEAN_PY_SCRIPT"
echo "✨ Cleanup finished."

# 3. Auto-detection and Upload
echo "📡 Starting upload from PC folder $APP_FOLDER..."

# Loop through all items in the target directory (asterisk OUTSIDE the quotes)
for item in "$APP_FOLDER"/*; do
    # Safety check: if the folder is empty, skip to avoid literal '*' processing
    [ -e "$item" ] || continue

    # Extract just the file/folder name (e.g., "main.py" instead of "./test_on_off/main.py")
    base_item=$(basename "$item")

    # Ignore the bash script itself, virtual environments, cache, and hidden files
    if [[ "$base_item" == "upload.sh" || "$base_item" == "venv" || "$base_item" == __pycache__* || "$base_item" == .* ]]; then
        continue
    fi

    if [ -d "$item" ]; then
        echo "📂 Uploading folder: $base_item/"
        uv run mpremote connect $PORT fs cp -r "$item" :
    elif [ -f "$item" ]; then
        echo "📄 Uploading file: $base_item"
        uv run mpremote connect $PORT fs cp "$item" :
    fi
done

# 4. Reboot
echo "🔄 Rebooting ESP32..."
uv run mpremote connect $PORT soft-reset

echo "✅ Deployment completed successfully!"

uv run mpremote
