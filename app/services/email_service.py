import logging
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return settings.SMTP_USER not in ("noreply@rozkaana.in", "your@gmail.com", "", "placeholder") \
        or settings.SMTP_PASSWORD not in ("your-zoho-password", "your-app-password", "")


class EmailService:
    async def _send(
        self,
        to: str,
        subject: str,
        html: str,
        attachments: list[tuple[str, bytes]] | None = None,
        use_menu_sender: bool = False,
    ) -> bool:
        if not _smtp_configured():
            logger.warning("SMTP not configured — email to %s skipped. Subject: %s", to, subject)
            return False

        # Route: menu@rozkaana.in for meal plan delivery, noreply@ for everything else
        if use_menu_sender and settings.SMTP_MENU_USER not in ("menu@rozkaana.in", "", "placeholder"):
            smtp_user = settings.SMTP_MENU_USER
            smtp_pass = settings.SMTP_MENU_PASSWORD
            from_email = settings.SMTP_MENU_USER
        else:
            smtp_user = settings.SMTP_USER
            smtp_pass = settings.SMTP_PASSWORD
            from_email = settings.SMTP_FROM_EMAIL

        try:
            msg = MIMEMultipart("mixed")
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html", "utf-8"))
            for filename, data in (attachments or []):
                part = MIMEApplication(data, Name=filename)
                part["Content-Disposition"] = f'attachment; filename="{filename}"'
                msg.attach(part)
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=smtp_user,
                password=smtp_pass,
                start_tls=True,
            )
            logger.info("Email sent [%s → %s] — %s", from_email, to, subject)
            return True
        except Exception as exc:
            logger.error("Email send failed [%s → %s]: %s", from_email, to, exc)
            return False

    async def send_otp(self, to: str, otp: str, name: str = "") -> bool:
        subject = f"{otp} is your Rozkaana OTP"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#FAF7F2;margin:0;padding:0}}
  .wrap{{max-width:520px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
  .header{{background:#E8593C;padding:32px 36px 24px;text-align:center}}
  .header h1{{color:#fff;font-size:22px;margin:0;font-weight:700}}
  .header p{{color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0}}
  .body{{padding:32px 36px}}
  .greeting{{font-size:15px;color:#3A3028;margin-bottom:20px}}
  .otp-box{{background:#FAF7F2;border:2px dashed #E8593C;border-radius:12px;padding:24px;text-align:center;margin:24px 0}}
  .otp-code{{font-size:42px;font-weight:800;letter-spacing:10px;color:#E8593C;font-family:'Courier New',monospace}}
  .otp-note{{font-size:12px;color:#7A6E65;margin-top:10px}}
  .footer{{background:#FAF7F2;padding:20px 36px;text-align:center;font-size:11px;color:#7A6E65;border-top:1px solid #E8DDD0}}
</style></head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🍱 Rozkaana</h1>
    <p>Your personalised Indian diet service</p>
  </div>
  <div class="body">
    <p class="greeting">Hi{' ' + name if name else ''},</p>
    <p style="color:#3A3028;font-size:14px">Use the OTP below to sign in to Rozkaana. It is valid for <strong>10 minutes</strong>.</p>
    <div class="otp-box">
      <div class="otp-code">{otp}</div>
      <div class="otp-note">Do not share this code with anyone.</div>
    </div>
    <p style="font-size:13px;color:#7A6E65">If you did not request this, you can safely ignore this email.</p>
  </div>
  <div class="footer">© 2026 Rozkaana · Made in India</div>
</div>
</body></html>"""
        return await self._send(to, subject, html)

    async def send_menu_card(
        self,
        to: str,
        name: str,
        menu_date: date,
        menu: dict,
        pdf_bytes: bytes | None = None,
        pdf_url: str | None = None,
    ) -> bool:
        date_str = menu_date.strftime("%A, %d %B %Y")
        subject = f"🍱 Your Rozkaana Meal Plan — {menu_date.strftime('%d %b')}"

        slot_defs = [
            ("breakfast",     "☀️", "Breakfast",      "8:00 AM"),
            ("morning_snack", "🍵", "Morning Snack",  "10:30 AM"),
            ("lunch",         "🍛", "Lunch",          "1:00 PM"),
            ("evening_snack", "🫐", "Evening Snack",  "4:30 PM"),
            ("dinner",        "🌙", "Dinner",         "8:00 PM"),
        ]

        rows = ""
        for key, icon, label, time in slot_defs:
            recipe = menu.get(key)
            if not recipe:
                continue
            rows += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #F2ECE3">
                <span style="font-size:18px">{icon}</span>
              </td>
              <td style="padding:12px 8px;border-bottom:1px solid #F2ECE3">
                <div style="font-size:10px;color:#7A6E65;text-transform:uppercase;letter-spacing:.08em">{label} · {time}</div>
                <div style="font-size:14px;font-weight:700;color:#1A1612;margin-top:2px">{recipe.get('name','—')}</div>
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #F2ECE3;text-align:right;white-space:nowrap">
                <span style="font-size:13px;font-weight:700;color:#E8593C">{recipe.get('calories',0)} kcal</span>
              </td>
            </tr>"""

        pdf_section = ""
        if pdf_url:
            pdf_section = f"""
            <div style="text-align:center;margin:28px 0 8px">
              <a href="{pdf_url}" target="_blank"
                style="display:inline-block;background:#E8593C;color:#fff;text-decoration:none;
                       padding:13px 32px;border-radius:10px;font-weight:700;font-size:14px">
                📄 View Full Meal Plan PDF
              </a>
            </div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#FAF7F2;margin:0;padding:0}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
  .header{{background:#E8593C;padding:28px 32px}}
  .header h1{{color:#fff;font-size:20px;margin:0;font-weight:700}}
  .header p{{color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0}}
  .macros{{display:flex;background:#1A1612;padding:16px 32px;gap:0}}
  .mac{{flex:1;text-align:center;color:#fff}}
  .mac .v{{font-size:18px;font-weight:800;color:#E8593C}}
  .mac .l{{font-size:10px;color:rgba(255,255,255,.5);text-transform:uppercase;margin-top:2px}}
  .body{{padding:8px 0}}
  table{{width:100%;border-collapse:collapse}}
  .footer{{background:#FAF7F2;padding:20px 32px;text-align:center;font-size:11px;color:#7A6E65;border-top:1px solid #E8DDD0}}
  .cmd-box{{background:#FAF7F2;border-radius:10px;padding:14px 20px;margin:16px 24px;font-size:12px;color:#7A6E65}}
  .cmd-box code{{background:#E8DDD0;padding:1px 5px;border-radius:3px;font-family:monospace;color:#3A3028}}
</style></head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🍱 Rozkaana — Your Meal Plan</h1>
    <p>📅 {date_str}</p>
  </div>
  <div class="macros">
    <div class="mac"><div class="v">{menu.get('total_calories',0)}</div><div class="l">kcal</div></div>
    <div class="mac"><div class="v">{menu.get('total_protein_g',0)}g</div><div class="l">protein</div></div>
    <div class="mac"><div class="v">{menu.get('total_carbs_g',0)}g</div><div class="l">carbs</div></div>
    <div class="mac"><div class="v">{menu.get('total_fat_g',0)}g</div><div class="l">fat</div></div>
  </div>
  <div class="body">
    <table>{rows}</table>
    {pdf_section}
  </div>
  <div class="cmd-box">
    💬 <strong>Reply commands:</strong>
    <code>regenerate</code> · <code>today south indian</code> · <code>help</code>
    <br><span style="font-size:11px;margin-top:6px;display:block">
      Visit <a href="https://rozkaana.in/dev" style="color:#E8593C">rozkaana.in/dev</a> for the full dev console.
    </span>
  </div>
  <div class="footer">© 2026 Rozkaana · Made in India · <a href="#" style="color:#E8593C">Unsubscribe</a></div>
</div>
</body></html>"""

        attachments = []
        if pdf_bytes:
            attachments.append((f"rozkaana-meal-plan-{menu_date}.pdf", pdf_bytes))

        return await self._send(to, subject, html, attachments if attachments else None, use_menu_sender=True)

    async def send_trial_start(self, to: str, name: str, trial_end: str) -> bool:
        subject = "Welcome to Rozkaana — Your 7-day free trial has started!"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#FAF7F2;margin:0;padding:0">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <div style="background:#E8593C;padding:32px 36px 24px;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">🎉 Welcome to Rozkaana!</h1>
    <p style="color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0">Your free trial has started</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028">Hi <strong>{name}</strong>,</p>
    <p style="color:#3A3028;font-size:14px;line-height:1.7">
      Your <strong>7-day free trial</strong> is now active. You'll receive a personalised Indian meal plan
      every morning — built around your body, your cuisine, and your health goals.
    </p>
    <div style="background:#FAF7F2;border-left:4px solid #E8593C;padding:14px 18px;border-radius:0 8px 8px 0;margin:20px 0">
      <div style="font-size:12px;color:#7A6E65">Trial active until</div>
      <div style="font-size:20px;font-weight:800;color:#E8593C">{trial_end}</div>
    </div>
    <p style="font-size:13px;color:#7A6E65">
      Your first meal plan will arrive tomorrow at 6:00 AM. Reply to any plan email with
      <code style="background:#F2ECE3;padding:1px 5px;border-radius:3px">help</code> to see available commands.
    </p>
  </div>
  <div style="background:#FAF7F2;padding:20px 36px;text-align:center;font-size:11px;color:#7A6E65;border-top:1px solid #E8DDD0">
    © 2026 Rozkaana · Made in India
  </div>
</div>
</body></html>"""
        return await self._send(to, subject, html)

    async def send_trial_expiry_warning(self, to: str, name: str, trial_end: str) -> bool:
        subject = "⚠️ Your Rozkaana trial ends in 2 days"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#FAF7F2;margin:0;padding:0">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)">
  <div style="background:#1A1612;padding:28px 36px;text-align:center">
    <h1 style="color:#fff;font-size:20px;margin:0">⏰ Trial ending soon</h1>
    <p style="color:rgba(255,255,255,.6);font-size:13px;margin:6px 0 0">Expires {trial_end}</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028">Hi <strong>{name}</strong>,</p>
    <p style="color:#3A3028;font-size:14px;line-height:1.7">
      Your free trial ends in <strong>2 days</strong> on {trial_end}.
      Subscribe to keep receiving your daily personalised meal plans.
    </p>
    <div style="text-align:center;margin:28px 0">
      <a href="https://rozkaana.in/#pricing" style="display:inline-block;background:#E8593C;color:#fff;text-decoration:none;padding:13px 32px;border-radius:10px;font-weight:700;font-size:14px">
        Continue with Rozkaana →
      </a>
    </div>
  </div>
  <div style="background:#FAF7F2;padding:20px 36px;text-align:center;font-size:11px;color:#7A6E65;border-top:1px solid #E8DDD0">
    © 2026 Rozkaana · Made in India
  </div>
</div>
</body></html>"""
        return await self._send(to, subject, html)


email_service = EmailService()
