from System import Uri, Net

def download_file(download_url, filename):
	web_client = Net.WebClient()
	web_client.DownloadFile(Uri(download_url), filename)
