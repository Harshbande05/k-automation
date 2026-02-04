from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
import requests
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")

with open("stores.json") as f:
    STORE_KEYS = json.load(f)


def get_profile_status(store_api_key: str, email: str) -> dict:
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
    subscriptions = profile["attributes"]["subscriptions"]

    email_marketing = subscriptions["email"]["marketing"]
    sms_marketing = subscriptions["sms"]["marketing"]
    sms_transactional = subscriptions["sms"]["transactional"]

    result = {}

    if email_marketing.get("suppression"):
        result["profile_status"] = email_marketing["suppression"][0].get(
            "reason", "USER_SUPPRESSED"
        )
    else:
        result["profile_status"] = "USER_ACTIVE"

    result["email_marketing"] = email_marketing.get("consent", "UNKNOWN")
    result["sms_marketing"] = sms_marketing.get("consent", "UNKNOWN")
    result["sms_transactional"] = sms_transactional.get("consent", "UNKNOWN")

    return result


# ---------- ROUTES ----------

@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stores": list(STORE_KEYS.keys())}
    )


@app.get("/check-profile")
def check_profile_page(request: Request):
    # Clean page on refresh
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stores": list(STORE_KEYS.keys())}
    )


@app.post("/check-profile")
def check_profile(
    request: Request,
    email: str = Form(...),
    store: str = Form(...)
):
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
