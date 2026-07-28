import sys
import textwrap

try:
    import requests
    import urllib3
except ModuleNotFoundError:
    print("Install 'requests' python package via 'pip install requests'")
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ver = "1.0.0"

banner = rf"""
┏┓┏┓┓   ┏┓┓ ┳
┃┃┃ ┃   ┃ ┃ ┃
┗┛┗┛┗┛  ┗┛┗┛┻
  {ver}
"""


def printmulti(string: str):
    print(textwrap.dedent(string).strip())

def do_logout(base_url: str, stoken: str):
    logout_url = f"{base_url}/admin/api/logout"
    headers = {"SToken": stoken}

    try:
        response = requests.post(
            logout_url, headers=headers, timeout=5, verify=False
        )
        if response.status_code == 200:
            print("Successfully logged out from server.")
        else:
            print(f"Server logout warning ({response.status_code}): {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Network error during logout: {e}")


def cli_loop(base_url: str, stoken: str):
    headers = {"SToken": stoken}

    while True:
        try:
            cmd = input("CLI> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            do_logout(base_url, stoken)
            sys.exit(0)

        if not cmd:
            continue

        if cmd.lower() in ("logout", "exit", "quit"):
            print("Logging out...")
            do_logout(base_url, stoken)
            print("Goodbye!")
            break

        elif cmd == "list-users":
            try:
                res = requests.get(
                    f"{base_url}/admin/api/list-all-users",
                    headers=headers,
                    verify=False,
                )
                if res.status_code == 200:
                    print(res.json())
                else:
                    print(f"Error ({res.status_code}): {res.text}")
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")

        else:
            print(f"Unknown command: '{cmd}'. Available: list-users, logout")


if __name__ == "__main__":
    printmulti(banner)

    print("Gathering system information...")
    oclipaddress = input("Enter the ip address of the OCL Server: ").strip()

    raw_port = input("Enter the port of the OCL Server [443]: ").strip()
    if not raw_port:
        oclport = 443
    else:
        try:
            oclport = int(raw_port)
        except ValueError:
            print(f"'{raw_port}' is not a valid port number.")
            sys.exit(1)

    raw_ssl = input("Is there ssl? (y/n): ").strip().lower()
    if raw_ssl in ["y", "yes"]:
        oclis_ssl = True
    elif raw_ssl in ["n", "no"]:
        oclis_ssl = False
    else:
        print("Invalid option. Please enter 'y' or 'n'.")
        sys.exit(1)

    print("\nGathering user information...")
    ocluser = input("Enter the user for backdoor admin: ").strip()
    oclpassword = input("Enter the password for user: ").strip()

    protocol = "https" if oclis_ssl else "http"
    base_url = f"{protocol}://{oclipaddress}:{oclport}"
    login_url = f"{base_url}/admin/api/login"

    print(f"\nAuthenticating with {base_url}...")

    stoken = None
    try:
        response = requests.post(
            login_url,
            json={"User": ocluser, "Password": oclpassword},
            timeout=10,
            verify=False,
        )

        if response.status_code == 201:
            stoken = response.json().get("token")
            print("Success: Authenticated successfully!\n")
        else:
            error_msg = response.json().get("error", "Unknown error")
            print(f"Failed ({response.status_code}): {error_msg}")
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"Connection error: Could not reach server at {base_url}")
        sys.exit(1)

    if stoken:
        cli_loop(base_url, stoken)