# Cube

Lambda-style command execution system.

## What is Cube?

Cube is a system for running commands (lamblets) on servers (lambdas) through a web interface. Think of it as a lightweight, self-hosted alternative to serverless functions.

## Concepts

| Term | Description |
|------|-------------|
| **Lambda** | A Docker container that runs commands |
| **Lamblet** | A command executed inside a lambda |

## How It Works

1. User launches a lambda (selects an OS image)
2. Lambda starts as a Docker container
3. User sends lamblets (commands) to the lambda via WebSocket or HTTP
4. Lambda executes the command and returns output
5. Lambda can be shut down when no longer needed

## Configuration

In `server/config.json`:

```json
{
    "cube": {
        "use": true,
        "islocal": true,
        "workers": ["tcp://localhost:2350"]
    }
}
```

| Field | Description |
|-------|-------------|
| `use` | Enable Cube at startup |
| `islocal` | Run lambdas locally (recommended for single-machine setups) |
| `workers` | Remote worker addresses for distributed setups |

## Available OS Images

The Cube IDE provides these base images:

- Fedora (Latest)
- Ubuntu (Latest)
- Python 3.11
- NodeJS 20
- Alpine Linux

## Web Interface

Access the Cube IDE at `/cube/index.html`. It provides:

- OS image selector
- Launch/shutdown controls
- Integrated terminal (xterm.js)
- Monaco code editor

## Requirements

- Docker installed and running
- Sufficient disk space for container images
