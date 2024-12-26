#!/bin/sh

# Start Ollama service in the background and redirect output to a log file
nohup ollama serve > /var/log/ollama.log 2>&1 &

# Give the service a moment to start up
sleep 5

# Pull the specified model
ollama pull ${MODEL}

# Start the application
exec "$@"
