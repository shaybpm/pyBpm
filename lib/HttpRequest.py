# -*- coding: utf-8 -*-
from System import Uri, Net
from System.Text import Encoding
import json


def download_file(download_url, filename):
    web_client = Net.WebClient()
    web_client.DownloadFile(Uri(download_url), filename)


def download_string(url):
    web_client = Net.WebClient()
    web_client.Encoding = Encoding.UTF8
    res = web_client.DownloadString(Uri(url))
    return res


def get(url):
    web_client = Net.WebClient()
    web_client.Encoding = Encoding.UTF8
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
