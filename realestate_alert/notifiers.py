from __future__ import annotations

import html
import os
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Protocol

from realestate_alert.models import Listing
from realestate_alert.naver import naver_land_url, naver_map_url

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
DEFAULT_PASSWORD_ENV = "GMAIL_APP_PASSWORD"


class Notifier(Protocol):
    def notify(self, listings: list[Listing]) -> None:
        raise NotImplementedError


class ConsoleNotifier:
    def notify(self, listings: list[Listing]) -> None:
        if not listings:
            print("신규 조건 매물이 없습니다.")
            return
        for listing in listings:
            print(format_listing_message(listing))


@dataclass
class MemoryNotifier:
    sent: list[Listing] = field(default_factory=list)

    def notify(self, listings: list[Listing]) -> None:
        self.sent.extend(listings)


@dataclass
class GmailNotifier:
    """신규 매물 발생 시 Gmail SMTP로 알림 메일을 발송한다.

    앱 비밀번호는 보안상 설정 파일이 아닌 환경 변수(password_env)에서 읽는다.
    """

    sender: str
    recipients: list[str]
    password_env: str = DEFAULT_PASSWORD_ENV
    smtp_factory: Callable[[], smtplib.SMTP] | None = None

    def notify(self, listings: list[Listing]) -> None:
        if not listings:
            return
        password = os.environ.get(self.password_env, "")
        if not password:
            print(
                f"[gmail] 환경 변수 {self.password_env}가 설정되지 않아 메일을 보내지 못했습니다. "
                "Google 계정 > 보안 > 앱 비밀번호에서 발급 후 설정하세요."
            )
            return
        message = build_email_message(self.sender, self.recipients, listings)
        try:
            with self._open_smtp() as smtp:
                smtp.login(self.sender, password)
                smtp.send_message(message)
            print(f"[gmail] 신규 매물 {len(listings)}건 알림 메일 발송 완료 → {', '.join(self.recipients)}")
        except (smtplib.SMTPException, OSError) as error:
            print(f"[gmail] 메일 발송 실패: {error}")

    def _open_smtp(self) -> smtplib.SMTP:
        if self.smtp_factory is not None:
            return self.smtp_factory()
        return smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30)


def build_email_message(sender: str, recipients: list[str], listings: list[Listing]) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = f"[210정형외과 매물 알림] 신규 매물 {len(listings)}건"
    message["From"] = sender
    message["To"] = ", ".join(recipients)

    plain = "\n\n".join(format_listing_message(listing) for listing in listings)
    message.attach(MIMEText(plain, "plain", "utf-8"))
    message.attach(MIMEText(build_email_html(listings), "html", "utf-8"))
    return message


def build_email_html(listings: list[Listing]) -> str:
    cards = "".join(_listing_card_html(listing) for listing in listings)
    return f"""\
<html>
  <body style="margin:0;padding:24px;background:#f4f7fa;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
    <div style="max-width:640px;margin:0 auto;">
      <h2 style="color:#0b3954;margin:0 0 4px;">210정형외과 신규 매물 알림</h2>
      <p style="color:#5b7083;margin:0 0 20px;">조건에 맞는 신규 매물 {len(listings)}건이 발견되었습니다.</p>
      {cards}
      <p style="color:#8899a6;font-size:12px;margin-top:24px;">
        본 메일은 부동산 매물 자동검색 서비스에서 발송되었습니다.
      </p>
    </div>
  </body>
</html>
"""


def _listing_card_html(listing: Listing) -> str:
    premium = "-" if listing.premium is None else f"{listing.premium:,}원"
    original_url = listing.url if listing.url.startswith(("http://", "https://")) else "#"
    return f"""\
<div style="background:#ffffff;border:1px solid #e1e8ef;border-radius:12px;padding:20px;margin-bottom:14px;">
  <p style="margin:0 0 6px;font-size:16px;font-weight:700;color:#102a43;">{html.escape(listing.title)}</p>
  <p style="margin:0 0 10px;color:#486581;">{html.escape(listing.location)}</p>
  <p style="margin:0 0 4px;color:#334e68;">
    보증금 {listing.deposit:,}원 / 월세 {listing.monthly_rent:,}원 · 면적 {listing.area_m2:g}㎡ · 권리금 {premium}
  </p>
  <p style="margin:12px 0 0;">
    <a href="{html.escape(naver_land_url(listing.location))}" style="color:#0967d2;font-weight:600;margin-right:14px;">네이버 부동산에서 보기</a>
    <a href="{html.escape(naver_map_url(listing.location))}" style="color:#0967d2;font-weight:600;margin-right:14px;">네이버 지도</a>
    <a href="{html.escape(original_url)}" style="color:#627d98;">원본 매물</a>
  </p>
</div>
"""


def format_listing_message(listing: Listing) -> str:
    premium = "-" if listing.premium is None else f"{listing.premium:,}원"
    floor = listing.floor or "-"
    return (
        "[신규 매물]\n"
        f"출처: {listing.source}\n"
        f"제목: {listing.title}\n"
        f"위치: {listing.location}\n"
        f"보증금: {listing.deposit:,}원 / 월세: {listing.monthly_rent:,}원\n"
        f"면적: {listing.area_m2:g}㎡ / 층: {floor} / 권리금: {premium}\n"
        f"네이버 부동산: {naver_land_url(listing.location)}\n"
        f"URL: {listing.url}"
    )
