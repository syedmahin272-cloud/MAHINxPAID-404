import json
import logging
import aiohttp
import asyncio
import re
import urllib.request
import urllib.error

# requests thakle use korbe, na thakle built-in urllib diye 60s timeout-e cholbe
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

BASE_URL = "https://hero-sms.com/stubs/handler_api.php"

# Telegram Checker API Credentials
CHECKER_URL = "http://api.agbots.site:8080/check/"
CHECKER_AUTH = "user8354"
CHECKER_API_KEY = "SIGUzg7Xf7euGs8B"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _sync_check_chunk(chunk_numbers: list) -> dict:
    payload = {
        "auth": CHECKER_AUTH,
        "api_key": CHECKER_API_KEY,
        "phone_numbers": chunk_numbers
    }

    if HAS_REQUESTS:
        try:
            resp = requests.get(CHECKER_URL, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                if str(data.get("status")) == "200":
                    return data.get("result_obj") or {}
                else:
                    logging.warning(f"Checker API error: {data}")
                    return {num: f"API_ERROR: {data.get('msg') or data}" for num in chunk_numbers}
        except Exception as e:
            logging.error(f"Checker requests failed: {e}")

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            CHECKER_URL,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "python-requests/2.31.0",
                "Accept": "*/*"
            },
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if str(data.get("status")) == "200":
                    return data.get("result_obj") or {}
    except Exception as e:
        logging.error(f"Checker urllib failed: {e}")

    return {num: "CHECK_FAILED" for num in chunk_numbers}


async def check_telegram_numbers(phone_numbers: list) -> dict:
    """Telegram number checker helper function"""
    if not phone_numbers:
        return {}

    unique_numbers = []
    seen = set()
    for p in phone_numbers:
        clean = re.sub(r'[^\d]', '', str(p))
        if 7 <= len(clean) <= 16:
            formatted = f"+{clean}"
            if formatted not in seen:
                seen.add(formatted)
                unique_numbers.append(formatted)

    if not unique_numbers:
        return {}

    all_results = {}
    chunk_size = 10

    for i in range(0, len(unique_numbers), chunk_size):
        chunk = unique_numbers[i:i + chunk_size]
        res_obj = await asyncio.to_thread(_sync_check_chunk, chunk)
        for k, v in res_obj.items():
            clean_k = re.sub(r'[^\d]', '', str(k))
            all_results[str(k)] = v
            all_results[f"+{clean_k}"] = v
            all_results[clean_k] = v

    return all_results


class HeroSMSClient:

    def __init__(self, api_key: str):
        self.api_key = api_key.strip().strip("\"'").strip() if api_key else ""

    async def _get(self, action: str, **kwargs):
        params = {"api_key": self.api_key, "action": action}
        params.update(kwargs)
        try:
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                async with session.get(
                    BASE_URL, params=params, timeout=15
                ) as response:
                    text = await response.text()
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
        except Exception as e:
            logging.error(f"API Error ({action}): {e}")
            return None

    async def get_balance(self):
        res = await self._get("getBalance")
        if isinstance(res, str):
            res_clean = res.strip()
            if res_clean.startswith("ACCESS_BALANCE:"):
                try:
                    return float(res_clean.split(":", 1)[1].strip())
                except:
                    return None
            try:
                return float(res_clean)
            except:
                pass
        elif isinstance(res, dict):
            if "balance" in res:
                try:
                    return float(res["balance"])
                except:
                    pass
            if (
                "data" in res
                and isinstance(res["data"], dict)
                and "balance" in res["data"]
            ):
                try:
                    return float(res["data"]["balance"])
                except:
                    pass
        return None

    async def get_prices(self, country: int = None, service: str = None):
        params = {}
        if country:
            params["country"] = country
        if service:
            params["service"] = service
        return await self._get("getPrices", **params)

    async def get_number(
        self, service: str, country: int, max_price: float = None, phone_exception: str = None
    ):
        params = {"service": service, "country": country}
        if max_price:
            params["maxPrice"] = max_price
        if phone_exception:
            params["phoneException"] = phone_exception
        return await self._get("getNumberV2", **params)

    async def get_status(self, activation_id: str):
        return await self._get("getStatus", id=activation_id)

    async def set_status(self, activation_id: str, status: int):
        return await self._get("setStatus", id=str(activation_id), status=status)

    async def get_active_activations(self):
        return await self._get("getActiveActivations")
