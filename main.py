from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
import requests
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Load store API keys
with open("stores.json") as f:
    STORE_KEYS = json.load(f)

def get_profile_status(store_api_key: str, email: str) -> dict:
    """
    Returns a dictionary with subscription status per channel for a single profile.
    If email does not exist, returns {"status": "USER DOES NOT EXIST"}
    """
    url = "https://a.klaviyo.com/api/profiles"
    headers = {
        "Authorization": f"Klaviyo-API-Key {store_api_key}",
        "accept": "application/vnd.api+json",
        "revision": "2026-01-15"
    }
    params = {
        "filter": f"equals(email,'{email}')",
        "additional-fields[profile]": "subscriptions"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
    except requests.RequestException:
        return {"error": "API request failed"}

    data = response.json().get("data", [])

    if not data:
        return {"status": "USER DOES NOT EXIST"}

    profile = data[0]
    subscriptions = profile["attributes"].get("subscriptions", {})
    result = {}

    # Loop through all channels
    for channel, channel_data in subscriptions.items():
        marketing = channel_data.get("marketing")
        if not marketing:
            continue

        # Determine subscription status
        if marketing.get("suppression") or marketing.get("list_suppressions"):
            result[channel] = "SUPPRESSED"
        elif marketing.get("can_receive_email_marketing") or \
             marketing.get("can_receive_sms_marketing") or \
             marketing.get("can_receive_push_marketing") or \
             marketing.get("can_receive"):
            result[channel] = "SUBSCRIBED"
        elif marketing.get("consent") == "UNSUBSCRIBED":
            result[channel] = "UNSUBSCRIBED"
        else:
            result[channel] = "NEVER SUBSCRIBED"

    return result

# --- Routes ---

@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stores": list(STORE_KEYS.keys())}
    )

@app.post("/check-profile")
def check_profile(request: Request, email: str = Form(...), store: str = Form(...)):
    api_key = STORE_KEYS.get(store)
    if not api_key:
        status = {"error": "Invalid store selected"}
    else:
        status = get_profile_status(api_key, email)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stores": list(STORE_KEYS.keys()),
            "email": email,
            "store": store,
            "status": status
        }
    )