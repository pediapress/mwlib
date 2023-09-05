"""Client to mw-serve"""

import argparse
import sys

import mwlib.myjson as json
from mwlib.client import Client


def main():
    parser = argparse.ArgumentParser()
    default_url = "http://localhost:8899/"
    parser.add_argument(
        "-u",
        "--url",
        help=f"URL of HTTP interface to mw-serve (default: {default_url})",
        default=default_url,
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Arguments for the command")

    options = parser.parse_args()

    command = options.command
    data = {}
    for arg in options.args:
        if "=" in arg:
            key, value = (x.strip() for x in arg.split("=", 1))
        else:
            key = arg.strip()
            value = True
        data[key] = value

    if "metabook" in data:
        with open(data["metabook"], "rb") as f:
            data["metabook"] = f.read()

    client = Client(options.url)
    if not client.request(command, data, is_json=(command != "download")):
        if client.error is not None:
            sys.exit(f"request failed: {client.error}")
        else:
            sys.exit(
                f"request failed: got response code {client.response_code}\n{client.response!r}"
            )

    if command == "download":
        fn = "output"
        with open(fn, "w") as f:
            f.write(client.response)
        print(f"wrote {len(client.response)} bytes to {fn!r}")
    else:
        print(json.dumps(client.response, indent=4))


if __name__ == "__main__":
    main()
