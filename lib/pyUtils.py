import json

def get_json_from_file(path):
	with open(path, 'r') as f:
		return json.load(f)
