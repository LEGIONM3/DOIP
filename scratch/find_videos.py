import urllib.request
import json
import urllib.parse

def search_repo_videos():
    queries = [
        "traffic+mp4",
        "surveillance+mp4",
        "highway+mp4",
        "uav+detection+mp4",
        "car+tracking+mp4"
    ]
    for q in queries:
        url = f"https://api.github.com/search/code?q=filename:.mp4+{q}&per_page=6"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                print(f"Query '{q}': {data.get('total_count', 0)} hits")
                for item in data.get("items", [])[:4]:
                    repo = item["repository"]["full_name"]
                    path = item["path"]
                    raw_url = f"https://raw.githubusercontent.com/{repo}/master/{path}"
                    print(f"  {repo} :: {path}")
        except Exception as e:
            print(f"Query '{q}' failed: {e}")

if __name__ == "__main__":
    search_repo_videos()
