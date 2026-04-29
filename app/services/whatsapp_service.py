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
        """
        Send daily meal plan. Uses session message with PDF link since
        WATI template requires pre-approval. Falls back to text with link.
        """
        number = phone.lstrip("+")
        date_str = menu_date.strftime("%d %B %Y")
        message = (
            f"🍱 *Rozkaana — Your Meal Plan*\n"
            f"📅 {date_str}\n\n"
            f"Your personalised meal plan is ready!\n"
            f"👉 View & Download PDF:\n{pdf_url}\n\n"
            f"Reply *help* for commands or *regenerate* for a new plan."
        )
        return await self.send_session_message(number, message)

    async def send_session_message(self, phone_number: str, message: str) -> bool:
        """Send session message (works within 24h of user interaction)."""
        number = phone_number.lstrip("+")
        url = f"{self.base_url}/api/v1/sendSessionMessage/{number}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    params={"messageText": message},
                    headers={"Authorization": settings.WATI_ACCESS_TOKEN},
                )
                success = resp.status_code == 200 and resp.json().get("result") is True
                if not success:
                    logger.warning("WATI session msg to %s: %s — %s", number, resp.status_code, resp.text[:200])
                else:
                    logger.info("WATI session msg sent to %s", number)
                return success
        except Exception as exc:
            logger.error("WATI session message failed: %s", exc)
            return False

    async def send_text(self, phone: str, message: str) -> bool:
        return await self.send_session_message(phone.lstrip("+"), message)

    async def send_template(self, phone: str, template_name: str, params: dict) -> bool:
        custom_params = [{"name": k, "value": v} for k, v in params.items()]
        payload = {
            "template_name": template_name,
            "broadcast_name": f"{template_name}_{phone}",
            "receivers": [{"whatsappNumber": phone.lstrip("+"), "customParams": custom_params}],
        }
        return await self._post("/api/v1/sendTemplateMessages", payload)

    async def opt_in_contact(self, phone: str, name: str) -> bool:
        # WATI creates contacts automatically on first template message
        return True

    async def _post(self, path: str, payload: dict) -> bool:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
                if resp.status_code == 429:
                    logger.warning("WATI rate limit hit")
                    return False
                ok = resp.status_code in (200, 201)
                if not ok:
                    logger.warning("WATI %s → %s: %s", path, resp.status_code, resp.text[:200])
                return ok
        except httpx.HTTPError as exc:
            logger.error("WATI request failed: %s", exc)
            return False


wa_service = WhatsAppService()
