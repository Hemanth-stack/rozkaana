import httpx
from app.config import settings

class WhatsAppService:
    def __init__(self, api_url: str, token: str):
        self.api_url = api_url.rstrip("/")
        self.headers = {"Authorization": token, "Content-Type": "application/json"}

    def _post(self, path: str, payload: dict) -> bool:
        url = f"{self.api_url}{path}"
        try:
            response = httpx.post(url, json=payload, headers=self.headers, timeout=10)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def send_meal_plan(self, phone: str, name: str, pdf_url: str, date: str) -> bool:
        payload = {
            "template_name": "rozkaana_daily_plan",
            "broadcast_name": f"daily_plan_{date}",
            "receivers": [{
                "whatsappNumber": phone,
                "customParams": [
                    {"name": "name", "value": name},
                    {"name": "date", "value": str(date)},
                    {"name": "pdf_url", "value": pdf_url}
                ]
            }]
        }
        return self._post("/api/v1/sendTemplateMessages", payload)

    def send_optin_request(self, phone: str, name: str) -> bool:
        payload = {
            "template_name": "rozkaana_optin",
            "broadcast_name": f"optin_{phone}",
            "receivers": [{
                "whatsappNumber": phone,
                "customParams": [{"name": "name", "value": name}]
            }]
        }
        return self._post("/api/v1/sendTemplateMessages", payload)

    def send_text(self, phone: str, text: str) -> bool:
        payload = {
            "broadcast_name": f"text_{phone}",
            "receivers": [{
                "whatsappNumber": phone,
                "message": text
            }]
        }
        return self._post("/api/v1/sendTextMessage", payload)

wa_service = WhatsAppService(settings.wati_api_url, settings.wati_access_token)