# -*- coding: utf-8 -*-
from System import Uri, Net
import json


def download_file(download_url, filename):
    web_client = Net.WebClient()
    web_client.DownloadFile(Uri(download_url), filename)


def get(url):
    web_client = Net.WebClient()
    res = web_client.DownloadString(Uri(url))
    return json.loads(res)


def post(url, data):
    web_client = Net.WebClient()
    web_client.Headers[Net.HttpRequestHeader.ContentType] = "application/json"
    res = web_client.UploadString(Uri(url), "POST", json.dumps(data))
    return json.loads(res)


def patch(url, data):
    web_client = Net.WebClient()
    web_client.Headers[Net.HttpRequestHeader.ContentType] = "application/json"
    res = web_client.UploadString(Uri(url), "PATCH", json.dumps(data))
    return json.loads(res)
