# OCloud

Media storage and command execution platform.

## What is OCloud?

OCloud is a self-hosted platform combining two core components:

- **OMedia** — Per-user file storage with authentication, admin dashboard, and file sharing
- **Cube** — Lambda-style system for running commands (lamblets) on remote servers (lambdas)

## Quick Start

### Docker (recommended)

```bash
docker compose up -d
```

### Native Python

```bash
cd server
python -m venv .avenv
source .avenv/Scripts/activate   # Windows/MSYS2
pip install -r requirements.txt
python server.py init             # initialize database
python server.py                  # start server
```

## Configuration

Edit `server/config.json` before starting. See [Configuration Reference](docs/configuration.md) for all options.

## Documentation

- [Configuration](docs/configuration.md)
- [OMedia](docs/omedia.md)
- [Cube](docs/cube.md)
- [Extensors](docs/extendors.md)
- [API Reference](docs/api.md)

## License

GNU General Public License v3.0

## Contributing

Contributions are welcome. Fork the repository, make changes in a branch, and submit a pull request.
