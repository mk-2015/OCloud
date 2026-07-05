# OMedia
![Logo](./server/root/logo.png)
Open Media storage system is a way to make your home have a cloud on permisis. Also homelabbing is the main purpose of this tool written in python.

## Usage
```bash
python -mvenv .venv
source .venv/bin/activate
cd server
pip install -r requirements.txt
python server.py
```

## Purpose
- Provide cloud storage for tech paranoid people
- Homelabbing purposes
- Learning python HTTP/S Networking

## What i allow to do
- Modify and share code
- Fork this repositry
- Contribute to this repositry
* License: GNU General Public License v3.0

## Example config.json
```json
{
    "host": "0.0.0.0",
    "port": 443,
    "ssl": 
    {
        "use": true,
        "keyfile": "./key.pem",
        "certfile": "./cert.pem"
    },
    "admin_password": "admin"
}
```

- Allows for admin dashboard.