from functools import lru_cache

# ==========================================
# MONKEY-PATCH REQUESTS TO BYPASS CLOUDFLARE
# ==========================================
import requests
from curl_cffi import requests as cffi_requests

def patched_get(*args, **kwargs):
    kwargs.pop("allow_redirects", None) # curl_cffi handles redirects slightly differently sometimes, but mostly it's fine
    kwargs["impersonate"] = "chrome"
    return cffi_requests.get(*args, **kwargs)

def patched_post(*args, **kwargs):
    kwargs.pop("allow_redirects", None)
    kwargs["impersonate"] = "chrome"
    return cffi_requests.post(*args, **kwargs)

requests.get = patched_get
requests.post = patched_post
# ==========================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from HdRezkaApi import HdRezkaApi, HdRezkaSearch

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=128)
def search_hdrezka(query: str, year: str = None):
    try:
        search = HdRezkaSearch("https://hdrezka.ag")
        results = search.fast_search(query)
        if not results:
            return None
            
        for r in results:
            if year and str(year) in r.get("url", ""):
                return r["url"]
        return results[0]["url"]
    except Exception as e:
        print(f"Search error: {e}")
        return None


@app.get("/api/search_rezka")
def api_search_rezka(title: str, year: str = None):
    url = search_hdrezka(title, year)
    if url:
        return {"success": True, "url": url}
    return {"success": False, "error": "Not found"}


@lru_cache(maxsize=128)
def fetch_info_cached(url: str):
    rezka = HdRezkaApi(url)
    return {
        "success": True,
        "title": rezka.name,
        "type": rezka.type,
        "translators": rezka.translators,
        "seriesInfo": rezka.seriesInfo if rezka.type in ["tv_series", "anime", "cartoon"] else None,
        "episodesInfo": rezka.episodesInfo if rezka.type in ["tv_series", "anime", "cartoon"] else None,
    }


@app.get("/api/info")
def get_info(url: str):
    try:
        return fetch_info_cached(url)
    except Exception as e:
        return {"success": False, "error": str(e)}


@lru_cache(maxsize=128)
def fetch_stream_cached(url: str, translator_id: str = None, season: str = None, episode: str = None):
    rezka = HdRezkaApi(url)
    if rezka.type in ["tv_series", "anime", "cartoon"]:
        stream = rezka.getStream(season, episode, translator_id)
    else:
        stream = rezka.getStream(translator_id)
        
    return stream.videos if stream else None


@app.get("/api/stream")
def get_stream(url: str, translator_id: str = None, season: str = None, episode: str = None):
    try:
        if translator_id == "null":
            translator_id = None
        if season == "null":
            season = None
        if episode == "null":
            episode = None
            
        data = fetch_stream_cached(url, translator_id, season, episode)
        return {"success": True, "streams": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
