# -*- coding: utf-8 -*-
import json

def get_json_from_file(path):
	f = open(path, 'r')
	res = json.load(f)
	f.close()
	return res

def findInList(list, cb_function):
    for item in list:
        if cb_function(item):
            return item
    return None
