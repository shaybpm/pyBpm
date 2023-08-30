import json

def get_json_from_file(path):
	f = open(path, 'r')
	res = json.load(f)
	f.close()
	return res
