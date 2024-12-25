FROM python:3.12.3-slim

ENV MODEL=llama3.1:8b

USER root
RUN curl -fsSL https://ollama.com/install.sh | sh
 
# Set the working directory
WORKDIR /app

COPY ./ ./

RUN ollame pull ${MODEL}

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]