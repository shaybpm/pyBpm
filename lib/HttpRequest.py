from System import Uri, Net
import json

def download_file(download_url, filename):
	web_client = Net.WebClient()
	web_client.DownloadFile(Uri(download_url), filename)

def get_request(url):
	web_client = Net.WebClient()
	res = web_client.DownloadString(Uri(url))
	return json.loads(res)
