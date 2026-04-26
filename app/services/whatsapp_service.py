import logging
from datetime import date

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self) -> None:
        self.base_url = settings.WATI_API_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": settings.WATI_ACCESS_TOKEN,
            "Content-Type": "application/json",
        }

    async def send_meal_plan(self, phone: str, name: str, pdf_url: str, menu_date: date) -> bool:
        payload = {
            "template_name": "nutriseva_daily_plan",
            "broadcast_name": f"daily_plan_{menu_date}",
            "receivers": [
                {
                    "whatsappNumber": phone.lstrip("+"),
                    "customParams": [
                        {"name": "name", "value": name or "there"},
                        {"name": "date", "value": menu_date.strftime("%d %B %Y")},
                        {"name": "pdf_url", "value": pdf_url},
                    ],
                }
            ],
        }
        return await self._post("/api/v1/sendTemplateMessages", payload)

    async def send_text(self, phone: str, message: str) -> bool:
        payload = {
            "broadcast_name": f"text_{phone}",
            "receivers": [
                {
                    "whatsappNumber": phone.lstrip("+"),
                    "message": message,
                }
            ],
        }
        return await self._post("/api/v1/sendTextMessage", payload)

    async def send_template(self, phone: str, template_name: str, params: dict) -> bool:
        custom_params = [{"name": k, "value": v} for k, v in params.items()]
        payload = {
            "template_name": template_name,
            "broadcast_name": f"{template_name}_{phone}",
            "receivers": [
                {
                    "whatsappNumber": phone.lstrip("+"),
                    "customParams": custom_params,
                }
            ],
        }
        return await self._post("/api/v1/sendTemplateMessages", payload)

    async def opt_in_contact(self, phone: str, name: str) -> bool:
        payload = {
            "name": name or "NutriSeva User",
            "phoneNumber": phone.lstrip("+"),
        }
        return await self._post("/api/v1/addContact", payload)

    async def _post(self, path: str, payload: dict) -> bool:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
                if resp.status_code == 429:
                    logger.warning("WATI rate limit hit, will retry on next attempt")
                    return False
                return resp.status_code in (200, 201)
        except httpx.HTTPError as exc:
            logger.error("WATI request failed: %s", exc)
            return False


wa_service = WhatsAppService()
