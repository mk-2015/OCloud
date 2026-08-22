import sys
import argparse
import requests
import json
import os
import textwrap
import urllib3

# Disable insecure request warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = os.path.expanduser("~/.ocloud_admin.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def authenticate(args):
    config = load_config()
    host = args.host or config.get("host")
    port = args.port or config.get("port", 443)
    ssl = args.ssl if args.ssl is not None else config.get("ssl", True)
    user = args.user or config.get("user")
    password = args.password or config.get("password")

    if not all([host, user, password]):
        print("Error: Missing required connection details (host, user, password).")
        sys.exit(1)

    protocol = "https" if ssl else "http"
    base_url = f"{protocol}://{host}:{port}"
    login_url = f"{base_url}/admin/api/login"

    try:
        response = requests.post(
            login_url,
            json={"User": user, "Password": password},
            timeout=10,
            verify=False,
        )
        if response.status_code == 201:
            token = response.json().get("token")
            # Save valid config
            save_config({"host": host, "port": port, "ssl": ssl, "user": user, "password": password})
            return base_url, token
        else:
            print(f"Authentication failed ({response.status_code}): {response.json().get('error', 'Unknown error')}")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        sys.exit(1)

def cmd_list_users(args):
    base_url, token = authenticate(args)
    headers = {"SToken": token}
    try:
        res = requests.get(f"{base_url}/admin/api/list-all-users", headers=headers, verify=False)
        if res.status_code == 200:
            print(json.dumps(res.json(), indent=2))
        else:
            print(f"Error ({res.status_code}): {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

def cmd_delete_user(args):
    base_url, token = authenticate(args)
    headers = {"SToken": token}
    try:
        res = requests.delete(f"{base_url}/admin/api/users/{args.username}", headers=headers, verify=False)
        if res.status_code == 200:
            print(res.json().get("message"))
        else:
            print(f"Error ({res.status_code}): {res.json().get('detail', res.text)}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

def cmd_list_logs(args):
    base_url, token = authenticate(args)
    headers = {"SToken": token}
    try:
        params = {"limit": args.limit}
        res = requests.get(f"{base_url}/admin/api/audit", headers=headers, params=params, verify=False)
        if res.status_code == 200:
            print(json.dumps(res.json().get("logs"), indent=2))
        else:
            print(f"Error ({res.status_code}): {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="OCloud Admin CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Shared auth arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--host", help="Server IP/Hostname")
    parent_parser.add_argument("--port", type=int, help="Server port")
    parent_parser.add_argument("--ssl", action="store_true", help="Use SSL")
    parent_parser.add_argument("--no-ssl", dest="ssl", action="store_false")
    parent_parser.add_argument("--user", help="Admin username")
    parent_parser.add_argument("--password", help="Admin password")

    # Users sub-command
    users_parser = subparsers.add_parser("users", help="Manage users")
    users_subparsers = users_parser.add_subparsers(dest="subcommand")
    
    list_users = users_subparsers.add_parser("list", help="List all users", parents=[parent_parser])
    list_users.set_defaults(func=cmd_list_users)
    
    del_user = users_subparsers.add_parser("delete", help="Delete a user", parents=[parent_parser])
    del_user.add_argument("username", help="Username to delete")
    del_user.set_defaults(func=cmd_delete_user)

    # Logs sub-command
    logs_parser = subparsers.add_parser("logs", help="Manage logs")
    logs_subparsers = logs_parser.add_subparsers(dest="subcommand")
    
    list_logs = logs_subparsers.add_parser("list", help="List audit logs", parents=[parent_parser])
    list_logs.add_argument("--limit", type=int, default=50, help="Number of logs to show")
    list_logs.set_defaults(func=cmd_list_logs)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
