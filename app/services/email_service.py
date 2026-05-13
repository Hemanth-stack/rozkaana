import logging
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)

# ── Shared HTML primitives ────────────────────────────────────────────────────

_HEADER_STYLE = (
    "font-family:'Segoe UI',Arial,sans-serif;background:#FAF7F2;margin:0;padding:0"
)
_WRAP_STYLE = (
    "max-width:560px;margin:32px auto;background:#fff;"
    "border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)"
)
_FOOTER_HTML = (
    '<div style="background:#FAF7F2;padding:20px 32px;text-align:center;'
    'font-size:11px;color:#7A6E65;border-top:1px solid #E8DDD0">'
    '&copy; 2026 Rozkaana &middot; Made in India &middot; '
    '<a href="https://rozkaana.in/settings" style="color:#E8593C;text-decoration:none">'
    'Manage preferences</a></div>'
)
_VIEWPORT = '<meta name="viewport" content="width=device-width,initial-scale=1.0">'


def _fmt(value, decimals: int = 1) -> str:
    """Format a float/Decimal to a clean string without unnecessary trailing zeros."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "0"
    if f == int(f):
        return str(int(f))
    return f"{f:.{decimals}f}".rstrip("0").rstrip(".")


def _smtp_configured() -> bool:
    return bool(settings.SMTP_USER) and bool(settings.SMTP_PASSWORD) \
        and settings.SMTP_USER not in ("your@gmail.com", "placeholder") \
        and settings.SMTP_PASSWORD not in ("your-zoho-password", "your-app-password")


def _menu_sender_configured() -> bool:
    return bool(settings.SMTP_MENU_USER) and bool(settings.SMTP_MENU_PASSWORD) \
        and settings.SMTP_MENU_USER not in ("placeholder",) \
        and settings.SMTP_MENU_PASSWORD not in ("your-zoho-menu-password",)


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

        if use_menu_sender and _menu_sender_configured():
            smtp_user  = settings.SMTP_MENU_USER
            smtp_pass  = settings.SMTP_MENU_PASSWORD
            from_email = settings.SMTP_MENU_USER
        else:
            smtp_user  = settings.SMTP_USER
            smtp_pass  = settings.SMTP_PASSWORD
            from_email = settings.SMTP_FROM_EMAIL

        try:
            msg = MIMEMultipart("mixed")
            msg["From"]    = f"{settings.SMTP_FROM_NAME} <{from_email}>"
            msg["To"]      = to
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

    # ── OTP ──────────────────────────────────────────────────────────────────

    async def send_otp(self, to: str, otp: str, name: str = "") -> bool:
        subject = f"{otp} is your Rozkaana OTP"
        greeting = f"Hi {name}," if name else "Hi,"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="background:#E8593C;padding:32px 36px 24px;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0;font-weight:700">Rozkaana</h1>
    <p style="color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0">Your personalised Indian diet service</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028;margin:0 0 16px">{greeting}</p>
    <p style="color:#3A3028;font-size:14px;margin:0 0 24px">
      Use the OTP below to sign in to Rozkaana. It is valid for <strong>10 minutes</strong>.
    </p>
    <div style="background:#FAF7F2;border:2px dashed #E8593C;border-radius:12px;padding:24px;text-align:center;margin:0 0 24px">
      <div style="font-size:42px;font-weight:800;letter-spacing:10px;color:#E8593C;font-family:'Courier New',monospace">{otp}</div>
      <div style="font-size:12px;color:#7A6E65;margin-top:10px">Do not share this code with anyone.</div>
    </div>
    <p style="font-size:13px;color:#7A6E65;margin:0">If you did not request this, you can safely ignore this email.</p>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)

    # ── Daily meal plan ───────────────────────────────────────────────────────

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
        subject  = f"&#127857; Your Rozkaana Meal Plan &mdash; {menu_date.strftime('%d %b')}"
        subject  = f"Your Rozkaana Meal Plan — {menu_date.strftime('%d %b')}"

        # ── Macro strip (table layout — works in all email clients) ──────────
        kcal    = menu.get("total_calories", 0)
        protein = _fmt(menu.get("total_protein_g", 0))
        carbs   = _fmt(menu.get("total_carbs_g", 0))
        fat     = _fmt(menu.get("total_fat_g", 0))

        _td = (
            'style="text-align:center;padding:14px 8px;'
            'border-right:1px solid rgba(255,255,255,.08)"'
        )
        _v  = 'style="font-size:18px;font-weight:800;color:#E8593C;display:block"'
        _l  = 'style="font-size:10px;color:rgba(255,255,255,.5);text-transform:uppercase;margin-top:3px;display:block"'

        macro_strip = f"""
<table width="100%" style="background:#1A1612;border-collapse:collapse">
  <tr>
    <td {_td}><span {_v}>{kcal}</span><span {_l}>kcal</span></td>
    <td {_td}><span {_v}>{protein}g</span><span {_l}>protein</span></td>
    <td {_td}><span {_v}>{carbs}g</span><span {_l}>carbs</span></td>
    <td style="text-align:center;padding:14px 8px">
      <span {_v}>{fat}g</span><span {_l}>fat</span>
    </td>
  </tr>
</table>"""

        # ── Meal rows ────────────────────────────────────────────────────────
        slot_defs = [
            ("breakfast",     "&#9728;&#65039;", "Breakfast",     "8:00 AM"),
            ("morning_snack", "&#127861;",        "Morning Snack", "10:30 AM"),
            ("lunch",         "&#127835;",        "Lunch",         "1:00 PM"),
            ("evening_snack", "&#129371;",        "Evening Snack", "4:30 PM"),
            ("dinner",        "&#127769;",        "Dinner",        "8:00 PM"),
        ]

        rows = ""
        for key, icon, label, time in slot_defs:
            recipe = menu.get(key)
            if not recipe:
                continue
            meal_kcal = recipe.get("calories", 0)
            rows += f"""
<tr>
  <td style="padding:14px 16px;border-bottom:1px solid #F2ECE3;width:36px;font-size:20px;vertical-align:middle">{icon}</td>
  <td style="padding:14px 8px;border-bottom:1px solid #F2ECE3;vertical-align:middle">
    <span style="display:block;font-size:10px;color:#7A6E65;text-transform:uppercase;letter-spacing:.08em">{label} &middot; {time}</span>
    <span style="display:block;font-size:15px;font-weight:700;color:#1A1612;margin-top:3px">{recipe.get("name", "—")}</span>
  </td>
  <td style="padding:14px 16px;border-bottom:1px solid #F2ECE3;text-align:right;white-space:nowrap;vertical-align:middle">
    <span style="font-size:13px;font-weight:700;color:#E8593C">{meal_kcal} kcal</span>
  </td>
</tr>"""

        # ── PDF button ───────────────────────────────────────────────────────
        pdf_section = ""
        if pdf_url:
            pdf_section = f"""
<tr>
  <td colspan="3" style="padding:24px 16px 8px;text-align:center">
    <a href="{pdf_url}" target="_blank"
       style="display:inline-block;background:#E8593C;color:#fff;text-decoration:none;
              padding:13px 32px;border-radius:10px;font-weight:700;font-size:14px">
      View Full Meal Plan PDF &rarr;
    </a>
  </td>
</tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">

  <!-- Header -->
  <div style="background:#E8593C;padding:28px 32px">
    <h1 style="color:#fff;font-size:20px;margin:0;font-weight:700">Rozkaana &mdash; Your Meal Plan</h1>
    <p style="color:rgba(255,255,255,.85);font-size:13px;margin:6px 0 0">&#128197; {date_str}</p>
  </div>

  <!-- Macro strip -->
  {macro_strip}

  <!-- Greeting -->
  <div style="padding:24px 24px 4px">
    <p style="font-size:15px;color:#1A1612;margin:0 0 6px">Hi {name},</p>
    <p style="font-size:13px;color:#7A6E65;margin:0">Here&rsquo;s your personalised meal plan for today.</p>
  </div>

  <!-- Meal table -->
  <table width="100%" style="border-collapse:collapse;margin-top:8px">
    {rows}
    {pdf_section}
  </table>

  <!-- App link -->
  <div style="padding:20px 24px;text-align:center">
    <a href="https://rozkaana.in/app"
       style="font-size:13px;color:#E8593C;text-decoration:none;font-weight:600">
      Open in Rozkaana &rarr;
    </a>
  </div>

  {_FOOTER_HTML}
</div>
</body></html>"""

        attachments = []
        if pdf_bytes:
            attachments.append((f"rozkaana-meal-plan-{menu_date}.pdf", pdf_bytes))

        return await self._send(to, subject, html, attachments or None, use_menu_sender=True)

    # ── Trial start ──────────────────────────────────────────────────────────

    async def send_trial_start(self, to: str, name: str, trial_end: str) -> bool:
        subject = "Welcome to Rozkaana — Your 7-day free trial has started!"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="background:#E8593C;padding:32px 36px 24px;text-align:center">
    <h1 style="color:#fff;font-size:22px;margin:0">Welcome to Rozkaana!</h1>
    <p style="color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0">Your free trial has started</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028;margin:0 0 14px">Hi <strong>{name}</strong>,</p>
    <p style="color:#3A3028;font-size:14px;line-height:1.7;margin:0 0 20px">
      Your <strong>7-day free trial</strong> is now active. You&rsquo;ll receive a personalised Indian meal plan
      every morning &mdash; built around your body, your cuisine, and your health goals.
    </p>
    <div style="background:#FAF7F2;border-left:4px solid #E8593C;padding:14px 18px;border-radius:0 8px 8px 0;margin:0 0 20px">
      <div style="font-size:12px;color:#7A6E65;margin-bottom:4px">Trial active until</div>
      <div style="font-size:20px;font-weight:800;color:#E8593C">{trial_end}</div>
    </div>
    <p style="font-size:13px;color:#7A6E65;margin:0">
      Your first meal plan will arrive tomorrow at 6:00 AM.
    </p>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)

    # ── Trial expiry warning ─────────────────────────────────────────────────

    async def send_trial_expiry_warning(self, to: str, name: str, trial_end: str) -> bool:
        subject = "Your Rozkaana trial ends in 2 days"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="background:#1A1612;padding:28px 36px;text-align:center">
    <h1 style="color:#fff;font-size:20px;margin:0">Trial ending soon</h1>
    <p style="color:rgba(255,255,255,.6);font-size:13px;margin:6px 0 0">Expires {trial_end}</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028;margin:0 0 14px">Hi <strong>{name}</strong>,</p>
    <p style="color:#3A3028;font-size:14px;line-height:1.7;margin:0 0 28px">
      Your free trial ends in <strong>2 days</strong> on {trial_end}.
      Subscribe to keep receiving your daily personalised meal plans.
    </p>
    <div style="text-align:center">
      <a href="https://rozkaana.in/billing"
         style="display:inline-block;background:#E8593C;color:#fff;text-decoration:none;
                padding:13px 32px;border-radius:10px;font-weight:700;font-size:14px">
        Continue with Rozkaana &rarr;
      </a>
    </div>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)

    # ── Subscription upgraded ────────────────────────────────────────────────

    async def send_subscription_upgraded(self, to: str, name: str, plan: str, next_billing: str) -> bool:
        plan_label = {"solo_basic": "Starter", "solo_pro": "Pro", "family": "Family"}.get(plan, plan)
        subject = f"You're now on the {plan_label} plan — Rozkaana"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="background:#2E7D52;padding:28px 36px;text-align:center">
    <h1 style="color:#fff;font-size:20px;margin:0">Plan Upgraded!</h1>
    <p style="color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0">Welcome to {plan_label}</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028;margin:0 0 14px">Hi <strong>{name}</strong>,</p>
    <p style="font-size:14px;color:#3A3028;line-height:1.7;margin:0 0 20px">
      You&rsquo;re now on the <strong>{plan_label} plan</strong>. Your personalised meal plans will continue without interruption.
    </p>
    <div style="background:#FAF7F2;border-radius:10px;padding:14px 18px;margin:0 0 20px;font-size:14px;color:#3A3028">
      <strong>Next billing:</strong> {next_billing}
    </div>
    <p style="font-size:13px;color:#7A6E65;margin:0">
      Visit <a href="https://rozkaana.in/billing" style="color:#E8593C">rozkaana.in/billing</a> to manage your subscription.
    </p>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)

    # ── Subscription cancelled ───────────────────────────────────────────────

    async def send_subscription_cancelled(self, to: str, name: str, active_until: str) -> bool:
        subject = "Your Rozkaana subscription has been cancelled"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="background:#1A1612;padding:28px 36px;text-align:center">
    <h1 style="color:#fff;font-size:20px;margin:0">Subscription Cancelled</h1>
    <p style="color:rgba(255,255,255,.6);font-size:13px;margin:6px 0 0">We&rsquo;re sorry to see you go</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:15px;color:#3A3028;margin:0 0 14px">Hi <strong>{name}</strong>,</p>
    <p style="font-size:14px;color:#3A3028;line-height:1.7;margin:0 0 24px">
      Your subscription has been cancelled. You&rsquo;ll continue to receive meal plans until <strong>{active_until}</strong>.
    </p>
    <div style="text-align:center">
      <a href="https://rozkaana.in/billing"
         style="display:inline-block;background:#E8593C;color:#fff;text-decoration:none;
                padding:12px 28px;border-radius:10px;font-weight:700;font-size:14px">
        Reactivate Plan
      </a>
    </div>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)

    # ── Household invite ─────────────────────────────────────────────────────

    async def send_household_invite(self, to: str, invited_by: str, invite_url: str) -> bool:
        subject = f"{invited_by} invited you to join Rozkaana"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="background:#E8593C;padding:28px 36px;text-align:center">
    <h1 style="color:#fff;font-size:20px;margin:0">You&rsquo;re Invited!</h1>
    <p style="color:rgba(255,255,255,.8);font-size:13px;margin:6px 0 0">Join a Rozkaana household plan</p>
  </div>
  <div style="padding:32px 36px">
    <p style="font-size:14px;color:#3A3028;line-height:1.7;margin:0 0 28px">
      <strong>{invited_by}</strong> has invited you to join their Rozkaana household meal plan.
      You&rsquo;ll get personalised daily meals while sharing recipes with your household.
    </p>
    <div style="text-align:center;margin:0 0 24px">
      <a href="{invite_url}"
         style="display:inline-block;background:#E8593C;color:#fff;text-decoration:none;
                padding:14px 32px;border-radius:10px;font-weight:700;font-size:15px">
        Join Household &rarr;
      </a>
    </div>
    <p style="font-size:12px;color:#7A6E65;text-align:center;margin:0">This invite expires in 48 hours.</p>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)

    # ── Account deleted ──────────────────────────────────────────────────────

    async def send_account_deleted(self, to: str, name: str) -> bool:
        subject = "Your Rozkaana account has been deleted"
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_VIEWPORT}</head>
<body style="{_HEADER_STYLE}">
<div style="{_WRAP_STYLE}">
  <div style="padding:32px 36px">
    <h2 style="color:#1A1612;margin:0 0 12px">Account Deleted</h2>
    <p style="font-size:14px;color:#3A3028;line-height:1.7;margin:0 0 16px">
      Hi <strong>{name}</strong>, your Rozkaana account and all associated data have been deleted.
    </p>
    <p style="font-size:13px;color:#7A6E65;margin:0">
      If this was a mistake, please contact us at
      <a href="mailto:support@rozkaana.in" style="color:#E8593C">support@rozkaana.in</a>
      within 7 days and we may be able to restore it.
    </p>
  </div>
  {_FOOTER_HTML}
</div>
</body></html>"""
        return await self._send(to, subject, html)


email_service = EmailService()
