"""
Air Cargo News -> Telegram / WhatsApp bildirim botu
---------------------------------------------------
Air cargo haber sitelerinin RSS akislarini kontrol eder, daha once
gormedigi her yeni haberi Telegram veya WhatsApp mesaji olarak gonderir.

Ilk calistirmada mevcut haberleri "gorulmus" olarak kaydeder, mesaj atmaz;
boylece sistem calismaya basladigi andan itibaren yeni haberler gelir.

Ortam degiskenleri (GitHub Secrets):
  META_TOKEN          : Meta WhatsApp Cloud API kalici erisim anahtari (System User token)
  META_PHONE_ID       : Meta panelindeki "Phone number ID" (gonderici test numarasi)
  META_TEMPLATE       : Onayli sablon adi (varsayilan: aircargo_news)
  META_TEMPLATE_LANG  : Sablon dili (varsayilan: en)
  TELEGRAM_TOKEN      : BotFather'in verdigi bot token'i  (Telegram kullanirsan)
  TELEGRAM_CHAT_ID    : Mesajlarin gidecegi sohbet ID'si  (Telegram kullanirsan)
  WA_PROVIDER         : Bos birakilirsa: META_TOKEN varsa "meta", TELEGRAM_TOKEN varsa "telegram",
                        yoksa "greenapi". Elle: "meta", "telegram", "greenapi", "callmebot", "twilio"
  WA_PHONE            : Mesajin gidecegi numara, uluslararasi formatta (or. +4915112345678)
  GREENAPI_URL        : GREEN-API konsolundaki apiUrl (or. https://7105.api.greenapi.com)
  GREENAPI_ID         : idInstance
  GREENAPI_TOKEN      : apiTokenInstance
  CALLMEBOT_APIKEY    : CallMeBot kullanirsan
  TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM : Twilio kullanirsan
"""

import json
import os
import re
import sys
import time
import html
from pathlib import Path
from urllib.parse import quote

import feedparser
import requests

# ---------------------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------------------

FEEDS = [
    {"name": "Air Cargo News", "url": "https://www.aircargonews.net/feed/"},
    {"name": "Air Cargo Week", "url": "https://aircargoweek.com/feed/"},
    {"name": "Payload Asia",   "url": "https://payloadasia.com/feed/"},
    # The Loadstar deniz/kara haberleri de yayinliyor; sadece "Air" kategorisini al:
    {"name": "The Loadstar",   "url": "https://theloadstar.com/feed/", "only_categories": ["Air"]},
    {"name": "CargoForwarder Global", "url": "https://www.cargoforwarder.eu/feed/"},
    {"name": "Cargo Facts",    "url": "https://www.cargofacts.com/feed/"},
    {"name": "Air Cargo World", "url": "https://aircargoworld.com/feed/"},
    {"name": "FreightWaves Air", "url": "https://www.freightwaves.com/news/tag/air-cargo/feed"},
    # Lojiport genel lojistik sitesi; sadece hava kargo ile ilgili haberleri al:
    {"name": "Lojiport",       "url": "https://www.lojiport.com/feed/",
     "only_keywords": ["kargo", "havayolu", "havalimanı", "havacılık", "uçak", "THY", "Turkish",
                       "Pegasus", "AJet", "cargo", "Orta Koridor"]},
]

# Bu kelimelerden biri baslikta ya da ozette gecerse mesaj 🔴 ile isaretlenir.
# Rakip / ortak / pazar listeni buradan istedigin gibi duzenle.
WATCHLIST = [
    "Turkish Cargo", "Turkish Airlines", "THY", "Istanbul", "Türk",
    "Qatar", "Emirates", "Lufthansa", "Cargolux", "Cathay", "Etihad",
    "Saudia", "Silk Way", "Atlas", "DSV", "DHL", "Kuehne", "EgyptAir",
    "Almaty", "Kazakhstan", "Central Asia", "Middle Corridor",
    "transpacific", "acquisition", "joint venture", "partnership", "interline",
]

# Sadece watchlist eslesen haberleri gondermek istersen True yap
ONLY_WATCHLIST = False

STATE_FILE = Path(__file__).parent / "seen.json"
MAX_SEEN = 8000            # dosya sismesin diye tutulacak son id sayisi
MAX_MESSAGES_PER_RUN = 20  # bir calismada gonderilecek azami mesaj
DELAY_BETWEEN_MSGS = 4     # saniye (CallMeBot hiz siniri icin)

# ---------------------------------------------------------------------------


def load_state():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data.get("seen", []), set(data.get("initialized_feeds", []))
    return [], set()


def save_state(seen, initialized_feeds):
    STATE_FILE.write_text(
        json.dumps({"initialized_feeds": sorted(initialized_feeds), "seen": seen[-MAX_SEEN:]},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def clean(text, limit=300):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    text = re.sub(r"The post .* appeared first on .*$", "", text).strip()
    return (text[:limit].rsplit(" ", 1)[0] + "…") if len(text) > limit else text


def entry_id(entry):
    return entry.get("id") or entry.get("guid") or entry.get("link")


def matches_category(entry, wanted):
    if not wanted:
        return True
    cats = {t.get("term", "").strip().lower() for t in entry.get("tags", [])}
    return any(w.lower() in cats for w in wanted)


def matches_keywords(text, wanted):
    if not wanted:
        return True
    low = text.lower()
    return any(w.lower() in low for w in wanted)


def title_key(title):
    """Ayni haberi farkli sitelerden iki kez gondermemek icin basligin sade hali."""
    return "t:" + re.sub(r"[^a-z0-9]+", "", title.lower())[:80]


def watch_hit(text):
    low = text.lower()
    return [w for w in WATCHLIST if w.lower() in low]


def fetch_new(seen_set):
    """Yeni haberleri ve basariyla okunan feed adlarini dondurur."""
    new_items, ok_feeds = [], set()
    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], timeout=30,
                                headers={"User-Agent": "Mozilla/5.0 (RSS reader; personal news alert)"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"[UYARI] {feed['name']} okunamadi: {e}", file=sys.stderr)
            continue
        if parsed.bozo and not parsed.entries:
            print(f"[UYARI] {feed['name']} gecersiz RSS dondurdu", file=sys.stderr)
            continue
        ok_feeds.add(feed["name"])

        for entry in parsed.entries:
            eid = entry_id(entry)
            if not eid or eid in seen_set:
                continue
            if not matches_category(entry, feed.get("only_categories")):
                seen_set.add(eid)  # bir daha kontrol etmeye gerek yok
                continue
            title = clean(entry.get("title", ""), 200)
            summary = clean(entry.get("summary", ""))
            if not matches_keywords(title + " " + summary, feed.get("only_keywords")):
                seen_set.add(eid)
                continue
            tkey = title_key(title)
            if tkey in seen_set:      # baska siteden ayni haber zaten geldi
                continue
            seen_set.add(tkey)
            new_items.append({
                "id": eid,
                "tkey": tkey,
                "source": feed["name"],
                "title": title,
                "summary": summary,
                "link": entry.get("link", ""),
                "ts": time.mktime(entry.published_parsed) if entry.get("published_parsed") else 0,
            })
    new_items.sort(key=lambda x: x["ts"])  # eskiden yeniye gonder
    return new_items, ok_feeds


def format_message(item):
    """Serbest metin mesaji + Meta sablonu icin 3 parametre dondurur."""
    hits = watch_hit(item["title"] + " " + item["summary"])
    flag = "🔴 " if hits else "✈️ "
    lines = [f"{flag}*{item['title']}*", f"_{item['source']}_"]
    if hits:
        lines.append("🎯 " + ", ".join(hits[:4]))
    if item["summary"]:
        lines += ["", item["summary"]]
    lines += ["", item["link"]]
    source = item["source"] + (" | 🎯 " + ", ".join(hits[:4]) if hits else "")
    meta_params = (source, flag + item["title"], item["link"])
    return "\n".join(lines), bool(hits), meta_params


def meta_param(text, limit):
    """Meta sablon parametresi: satir sonu/tab ve 4+ bosluk yasak."""
    text = re.sub(r"\s+", " ", text or "").strip() or "-"
    return text[:limit]


def provider_name():
    if os.environ.get("WA_PROVIDER", "").strip():
        return os.environ["WA_PROVIDER"].strip().lower()
    if os.environ.get("META_TOKEN", "").strip():
        return "meta"
    if os.environ.get("TELEGRAM_TOKEN", "").strip():
        return "telegram"
    return "greenapi"


def send_meta_template(params):
    phone = re.sub(r"\D", "", os.environ["WA_PHONE"])
    limits = (120, 400, 400)
    r = requests.post(
        f"https://graph.facebook.com/{os.environ.get('META_API_VERSION') or 'v25.0'}"
        f"/{os.environ['META_PHONE_ID'].strip()}/messages",
        headers={"Authorization": f"Bearer {os.environ['META_TOKEN'].strip()}"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": (os.environ.get("META_TEMPLATE") or "aircargo_news").strip(),
                "language": {"code": (os.environ.get("META_TEMPLATE_LANG") or "en").strip()},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": meta_param(p, n)}
                                   for p, n in zip(params, limits)],
                }],
            },
        },
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Meta WhatsApp gonderimi basarisiz ({r.status_code}): {r.text[:300]}")


def to_telegram_html(text):
    """WhatsApp bicimini (*kalin*, _italik_) Telegram HTML'ine cevirir."""
    out = []
    for line in html.escape(text, quote=False).split("\n"):
        line = re.sub(r"^(\S* ?)\*(.+)\*$", r"\1<b>\2</b>", line)
        line = re.sub(r"^_(.+)_$", r"<i>\1</i>", line)
        out.append(line)
    return "\n".join(out)


def send_whatsapp(text, meta_params=None):
    provider = provider_name()

    if provider == "meta":
        send_meta_template(meta_params or ("Air Cargo Bot", text, repo_url()))
        return

    if provider == "telegram":
        r = requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN'].strip()}/sendMessage",
            json={"chat_id": os.environ["TELEGRAM_CHAT_ID"].strip(), "text": to_telegram_html(text),
                  "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=30,
        )
        if r.status_code >= 300:
            raise RuntimeError(f"Telegram gonderimi basarisiz ({r.status_code}): {r.text[:200]}")
        return

    phone = os.environ["WA_PHONE"].strip()
    if provider == "greenapi":
        base = (os.environ.get("GREENAPI_URL") or "https://api.green-api.com").strip().rstrip("/")
        r = requests.post(
            f"{base}/waInstance{os.environ['GREENAPI_ID'].strip()}/sendMessage/{os.environ['GREENAPI_TOKEN'].strip()}",
            json={"chatId": re.sub(r"\D", "", phone) + "@c.us", "message": text, "linkPreview": False},
            timeout=30,
        )
    elif provider == "twilio":
        sid, token = os.environ["TWILIO_SID"], os.environ["TWILIO_TOKEN"]
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"From": os.environ.get("TWILIO_FROM", "whatsapp:+14155238886"),
                  "To": f"whatsapp:{phone}", "Body": text},
            timeout=30,
        )
    else:
        r = requests.get(
            "https://api.callmebot.com/whatsapp.php"
            f"?phone={quote(phone)}&text={quote(text)}&apikey={os.environ['CALLMEBOT_APIKEY']}",
            timeout=60,
        )
    if r.status_code >= 300:
        raise RuntimeError(f"WhatsApp gonderimi basarisiz ({r.status_code}): {r.text[:200]}")


def repo_url():
    srv, repo = os.environ.get("GITHUB_SERVER_URL"), os.environ.get("GITHUB_REPOSITORY")
    return f"{srv}/{repo}" if srv and repo else "https://github.com"


def main():
    seen, initialized_feeds = load_state()
    first_ever = not initialized_feeds
    seen_set = set(seen)
    items, ok_feeds = fetch_new(seen_set)

    # Ilk kez basariyla okunan feed'lerin mevcut haberlerini sessizce kaydet
    # (bot ilk kurulduğunda veya listeye yeni site eklendiginde eski haber yagmuru olmasin)
    fresh_feeds = ok_feeds - initialized_feeds
    if fresh_feeds:
        baseline = [i for i in items if i["source"] in fresh_feeds]
        seen += [x for i in baseline for x in (i["id"], i["tkey"])]
        initialized_feeds |= fresh_feeds
        items = [i for i in items if i["source"] not in fresh_feeds]
        print(f"Baslangic kaydi: {', '.join(sorted(fresh_feeds))} ({len(baseline)} mevcut haber, mesaj atilmadi)")
        if first_ever:
            try:
                send_whatsapp("✅ Air cargo haber botu aktif. Takip edilen siteler: "
                              + ", ".join(sorted(fresh_feeds)) + ". Yeni haberler buraya gelecek.")
            except Exception as e:
                print(f"[UYARI] Test mesaji gonderilemedi: {e}", file=sys.stderr)

    sent = 0
    for item in items:
        msg, is_hit, meta_params = format_message(item)
        if ONLY_WATCHLIST and not is_hit:
            seen += [item["id"], item["tkey"]]
            continue
        if sent >= MAX_MESSAGES_PER_RUN:
            break  # kalanlar bir sonraki calismada gider
        try:
            send_whatsapp(msg, meta_params)
            sent += 1
            seen += [item["id"], item["tkey"]]
            time.sleep(DELAY_BETWEEN_MSGS)
        except Exception as e:
            print(f"[HATA] {item['title']}: {e}", file=sys.stderr)
            break  # gonderilemeyen haber gorulmemis kalir, sonra tekrar denenir

    save_state(seen, initialized_feeds)
    print(f"{len(items)} yeni haber bulundu, {sent} mesaj gonderildi.")


if __name__ == "__main__":
    main()
