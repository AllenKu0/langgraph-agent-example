# AI Agent with Tool Calling Capability

This project implements an AI Agent using LangGraph, which can call a tool function and handle missing parameters. The project is API-ified using FastAPI.

## Project Structure

- `app.py`: Contains the AI Agent logic and FastAPI setup.
- `tool.py`: Contains the actual tool function that the AI Agent will call.
- `requirements.txt`: Lists the required Python packages.

## Setup Instructions

### Prerequisites

- Python 3.12.3
- pip (Python package installer)

### Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/AllenKu0/langgraph-agent-example.git
    cd langgraph-agent-example
    ```

2. Install the required packages:

    ```sh
    pip install -r requirements.txt
    ```

### Running the Application

To start the FastAPI server, run:

```sh
pyhton app.py
```
