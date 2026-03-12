import os
import requests
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"

OUT_DIR = "pubchem_raw_json"
os.makedirs(OUT_DIR, exist_ok=True)
REQUEST_TIMEOUT_SECONDS = 20


def _build_retry_session():
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_retry_session()


def get_cid_by_name(name):
    url = f"{BASE_URL}/compound/name/{name}/cids/JSON"
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()["IdentifierList"]["CID"][0]


def download_json(url):
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def save_json(data, filename):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] Saved: {path}")


def process_input(term):
    term = term.strip()

    # Allow CID input directly
    if term.isdigit():
        cid = int(term)
    else:
        cid = get_cid_by_name(term)

    print(f"CID resolved: {cid}")

    # Full record JSON
    record_url = f"{BASE_URL}/compound/cid/{cid}/record/JSON"
    record_json = download_json(record_url)
    save_json(record_json, f"{term.replace(' ','_')}_{cid}_record.json")

    # PUG-View JSON (contains Safety and Hazards tree)
    view_url = f"{VIEW_URL}/{cid}/JSON"
    view_json = download_json(view_url)
    save_json(view_json, f"{term.replace(' ','_')}_{cid}_pugview.json")

    print("Done.\n")


if __name__ == "__main__":
    user_input = input("Enter compound name(s) or CID(s), comma separated: ")
    items = [x.strip() for x in user_input.split(",") if x.strip()]

    for item in items:
        print("=" * 60)
        process_input(item)
        time.sleep(1)