FROM python:3.12.3-slim

ENV MODEL=llama3.1:8b

USER root

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh
 
# Copy and make the entrypoint script executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set the working directory
WORKDIR /app

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt
# RUN ollama pull ${MODEL}
# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app.py"]
