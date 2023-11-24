import requests
import json

json_file_path = "/home/fingon/Dev/pediapress/mwlib/src/mwlib/core/example.json"


with open(json_file_path) as json_file:
    data = json.load(json_file)


response = requests.post("http://localhost:8899/", data=data)
