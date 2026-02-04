from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests
import json

# Initialize FastAPI app
app = FastAPI()

# Configure Jinja templates directory
templates = Jinja2Templates(directory="templates")

# Load store name -> Klaviyo API key mapping
with open("stores.json") as f:
    STORE_KEYS = json.load(f)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Temporary in-memory storage for last lookup result
LAST_RESULT = None


def get_profile_status(store_api_key: str, email: str) -> dict:
    """
    Fetch Klaviyo profile subscription status for a given email.

    Args:
        store_api_key (str): Klaviyo private API key for the selected store.
        email (str): Email address to lookup.

    Returns:
        dict: Profile status including email marketing, SMS marketing,
              SMS transactional consent, or error/status messages.
    """
    url = "https://a.klaviyo.com/api/profiles"
    headers = {
        "Authorization": f"Klaviyo-API-Key {store_api_key}",
        "accept": "application/vnd.api+json",
        "revision": "2026-01-15",
    }
    params = {
        "filter": f"equals(email,'{email}')",
        "additional-fields[profile]": "subscriptions",
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
        reason = email_marketing["suppression"][0].get("reason")
        result["profile_status"] = f"USER_SUPPRESSED, reson: {reason}"
    else:
        result["profile_status"] = "USER_ACTIVE"

    result["email_marketing"] = email_marketing.get("consent", "UNKNOWN")
    result["sms_marketing"] = sms_marketing.get("consent", "UNKNOWN")
    result["sms_transactional"] = sms_transactional.get("consent", "UNKNOWN")

    return result


@app.get("/")
def dashboard(request: Request):
    """
    Render dashboard page with store selector and email input form.
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stores": list(STORE_KEYS.keys())},
    )


@app.post("/check-profile")
def check_profile(email: str = Form(...), store: str = Form(...)):
    """
    Handle form submission, call Klaviyo API, and store result temporarily.
    Redirects to /result to display output.
    """
    global LAST_RESULT

    api_key = STORE_KEYS.get(store)

    if not api_key:
        LAST_RESULT = {
            "email": email,
            "store": store,
            "status": {"error": "Invalid store selected"},
        }
    else:
        status = get_profile_status(api_key, email)
        LAST_RESULT = {
            "email": email,
            "store": store,
            "status": status,
        }

    return RedirectResponse(url="/result", status_code=303)


@app.get("/result")
def show_result(request: Request):
    """
    Render result page using the last stored lookup.
    Clears the stored result after rendering to avoid stale data on refresh.
    """
    global LAST_RESULT

    if not LAST_RESULT:
        return RedirectResponse(url="/", status_code=303)

    result = LAST_RESULT
    LAST_RESULT = None

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stores": list(STORE_KEYS.keys()),
            "email": result["email"],
            "store": result["store"],
            "status": result["status"],
        },
    )