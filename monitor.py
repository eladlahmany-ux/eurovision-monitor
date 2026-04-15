import os
import time
import smtplib
import logging
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# --- Config from environment variables ---
EMAIL_FROM     = os.environ["EMAIL_FROM"]      # Gmail address you send FROM
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]  # Gmail App Password (16 chars)
EMAIL_TO       = os.environ["EMAIL_TO"]        # Where to send the alert
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL_MINUTES", "10")) * 60

TARGET_URL = "https://www.fansale.at/tickets/all/eurovision-song-contest/502368"

FINAL_KEYWORDS = [
    "grand final", "großes finale", "grande finale",
    "finale", "grand finale", "גמר"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}


def fetch_page():
    resp = requests.get(TARGET_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def find_final_tickets(html: str):
    """Return list of ticket listings that mention the Grand Final."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Each listing is typically in a row / card — look broadly
    for tag in soup.find_all(["li", "div", "tr", "article"]):
        text = tag.get_text(" ", strip=True).lower()
        if any(kw in text for kw in FINAL_KEYWORDS):
            # Make sure there's actual ticket content (price / category info)
            if any(c in text for c in ["€", "eur", "cat", "block", "standing", "seated"]):
                results.append(tag.get_text(" ", strip=True)[:300])

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def send_email(listings):
    subject = "🎤 נמצאו כרטיסים לגמר האירוויזיון ב-Fansale!"

    body_lines = [
        "שלום,",
        "",
        "נמצאו כרטיסים לגמר האירוויזיון ב-Fansale.at!",
        "",
        f"קישור: {TARGET_URL}",
        "",
        "פרטי המשרות שנמצאו:",
        "",
    ]
    for i, listing in enumerate(listings, 1):
        body_lines.append(f"{i}. {listing}")
        body_lines.append("")

    body_lines += [
        "---",
        f"נשלח ב-{datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "המעקב הסתיים לאחר מציאת כרטיסים."
    ]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText("\n".join(body_lines), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    log.info("Email sent to %s", EMAIL_TO)


def main():
    log.info("Eurovision Final Ticket Monitor started")
    log.info("Checking every %d minutes", CHECK_INTERVAL // 60)
    log.info("Target: %s", TARGET_URL)

    while True:
        try:
            log.info("Fetching page...")
            html = fetch_page()
            listings = find_final_tickets(html)

            if listings:
                log.info("Found %d final ticket listing(s)! Sending email...", len(listings))
                send_email(listings)
                log.info("Done. Exiting.")
                break
            else:
                log.info("No Grand Final tickets found. Next check in %d minutes.", CHECK_INTERVAL // 60)

        except requests.RequestException as e:
            log.warning("Network error: %s — will retry next interval", e)
        except Exception as e:
            log.error("Unexpected error: %s", e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
