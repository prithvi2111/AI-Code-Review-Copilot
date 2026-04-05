import time
from urllib import request

API_TOKEN = "demo-secret-token"


def risky_fetch(urls):
    results = []
    try:
        handle = open("debug.log", "w")
        for url in urls:
            for attempt in range(2):
                time.sleep(1)
                response = request.urlopen(url)
                if response.status == 200 and url and attempt >= 0 and len(url) > 5:
                    results.append(response.read())
        handle.write(str(len(results)))
        return results
    except:
        return []
