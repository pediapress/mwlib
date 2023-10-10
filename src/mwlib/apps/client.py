"""Client to mw-serve"""

import argparse
import sys

import mwlib.utilities.myjson as json
from mwlib.networking.client import Client


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
        with open(data["metabook"], "rb") as metabook_file:
            data["metabook"] = metabook_file.read()

    client = Client(options.url)
    if not client.request(command, data, is_json=(command != "download")):
        if client.error is not None:
            sys.exit(f"request failed: {client.error}")
        else:
            sys.exit(
                f"request failed: got response code {client.response_code}\n{client.response!r}"
            )

    if command == "download":
        filename = "output"
        with open(filename, "w") as out_file:
            out_file.write(client.response)
        print(f"wrote {len(client.response)} bytes to {filename!r}")
    else:
        print(json.dumps(client.response, indent=4))


if __name__ == "__main__":
    main()
