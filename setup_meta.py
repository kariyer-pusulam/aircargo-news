"""
Meta WhatsApp Cloud API kurulum kontrolu (GitHub Actions'ta "Meta kurulum" isiyle calisir).

1) Erisim anahtarini ve gonderici numarayi kontrol eder
2) Meta'nin hazir "hello_world" test mesajini sana gonderir
3) Haber sablonunu (aircargo_news) yoksa olusturur, durumunu raporlar
4) Sablon onayliysa ornek bir haber mesaji gonderir

Gerekli secret'lar: META_TOKEN, META_PHONE_ID, META_WABA_ID, WA_PHONE
Tekrar tekrar calistirilabilir; sablon zaten varsa yeniden olusturmaz.
"""

import os
import re
import sys

import requests

VERSION = os.environ.get("META_API_VERSION") or "v25.0"
API = f"https://graph.facebook.com/{VERSION}"
TEMPLATE = (os.environ.get("META_TEMPLATE") or "aircargo_news").strip()
LANG = (os.environ.get("META_TEMPLATE_LANG") or "en").strip()

TEMPLATE_BODY = (
    "New air cargo news from {{1}}:\n\n"
    "{{2}}\n\n"
    "Read the full story: {{3}}\n\n"
    "You receive this because you subscribed to the Air Cargo News Bot."
)
TEMPLATE_EXAMPLE = [
    "Air Cargo News",
    "Turkish Cargo signs interline agreement with EgyptAir Cargo",
    "https://www.aircargonews.net/airlines/2026/10/example-story/",
]


def env(name):
    val = (os.environ.get(name) or "").strip()
    if not val:
        fail(f"'{name}' secret'i tanimli degil. Settings > Secrets and variables > Actions altindan ekle.")
    return val


def fail(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def explain(r):
    try:
        err = r.json().get("error", {})
        return f"{err.get('code')} / {err.get('error_subcode', '-')}: {err.get('message')}"
    except Exception:
        return r.text[:300]


def main():
    token, phone_id, waba_id = env("META_TOKEN"), env("META_PHONE_ID"), env("META_WABA_ID")
    to = re.sub(r"\D", "", env("WA_PHONE"))
    h = {"Authorization": f"Bearer {token}"}

    # 1) Token + gonderici numara
    print("1) Erisim anahtari ve gonderici numara kontrol ediliyor...")
    r = requests.get(f"{API}/{phone_id}", headers=h,
                     params={"fields": "display_phone_number,verified_name"}, timeout=30)
    if r.status_code != 200:
        hint = ""
        if r.status_code == 401 or "expired" in r.text.lower():
            hint = "\n   -> Token gecersiz ya da suresi dolmus. README'deki 'kalici token' adimini uygula."
        fail(f"Gonderici numara okunamadi ({explain(r)}){hint}")
    info = r.json()
    print(f"   ✓ Gonderici: {info.get('display_phone_number')} ({info.get('verified_name')})")

    # 2) hello_world testi
    print(f"2) Meta'nin hazir 'hello_world' test mesaji +{to} numarasina gonderiliyor...")
    r = requests.post(f"{API}/{phone_id}/messages", headers=h, timeout=30, json={
        "messaging_product": "whatsapp", "to": to, "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    })
    if r.status_code != 200 and "132001" in r.text:
        print("   - Bu test hesabinda 'hello_world' sablonu yok, bu adim atlaniyor.")
    elif r.status_code != 200:
        hint = ""
        if "131030" in r.text:
            hint = ("\n   -> Numaran test numarasinin alici listesinde degil. Meta panelinde "
                    "WhatsApp > API Setup > 'To' alanina numarani ekle ve gelen kodla dogrula.")
        fail(f"Test mesaji gonderilemedi ({explain(r)}){hint}")
    else:
        print("   ✓ Gonderildi. WhatsApp'ina 'Hello World' mesaji gelmeli.")

    # 3) Haber sablonu
    print(f"3) '{TEMPLATE}' sablonu kontrol ediliyor...")
    r = requests.get(f"{API}/{waba_id}/message_templates", headers=h, timeout=30,
                     params={"name": TEMPLATE, "fields": "name,status,category,language,rejected_reason"})
    if r.status_code != 200:
        fail(f"Sablonlar okunamadi ({explain(r)})\n   -> META_WABA_ID dogru mu? Token'a "
             "whatsapp_business_management izni verildi mi?")
    tpl = next((t for t in r.json().get("data", [])
                if t.get("name") == TEMPLATE and t.get("language") == LANG), None)

    if not tpl:
        print("   Sablon yok, olusturuluyor...")
        r = requests.post(f"{API}/{waba_id}/message_templates", headers=h, timeout=30, json={
            "name": TEMPLATE, "language": LANG, "category": "UTILITY",
            "components": [{"type": "BODY", "text": TEMPLATE_BODY,
                            "example": {"body_text": [TEMPLATE_EXAMPLE]}}],
        })
        if r.status_code != 200:
            fail(f"Sablon olusturulamadi ({explain(r)})")
        tpl = {"status": r.json().get("status", "PENDING"), "category": r.json().get("category", "UTILITY")}
        print("   ✓ Sablon Meta'ya onaya gonderildi.")

    status, category = tpl.get("status"), tpl.get("category")
    print(f"   Durum: {status} | Kategori: {category}")

    if status == "APPROVED":
        # 4) Ornek haber
        print("4) Sablon onayli, ornek haber gonderiliyor...")
        r = requests.post(f"{API}/{phone_id}/messages", headers=h, timeout=30, json={
            "messaging_product": "whatsapp", "to": to, "type": "template",
            "template": {"name": TEMPLATE, "language": {"code": LANG}, "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": "Kurulum testi"},
                               {"type": "text", "text": "✅ Meta kurulumu tamam. Haberler bu formatta gelecek."},
                               {"type": "text", "text": TEMPLATE_EXAMPLE[2]}],
            }]},
        })
        if r.status_code != 200:
            fail(f"Ornek haber gonderilemedi ({explain(r)})")
        print("   ✓ Gonderildi.")
        if category != "UTILITY":
            print(f"\n⚠️  Meta sablonu '{category}' olarak siniflandirdi. Calisir, ancak Meta pazarlama "
                  "mesajlarinda kisi basi gunluk sinir uygulayabildigi icin bazi haberler teslim edilmeyebilir.")
        print("\n🎉 Her sey hazir. Simdi 'Air Cargo News Alerts' isini calistirabilirsin.")
    elif status in ("PENDING", "IN_APPEAL", None):
        print("\n⏳ Sablon Meta onayi bekliyor (genelde birkac dakika, bazen birkac saat).")
        print("   Bu isi 15-30 dakika sonra tekrar calistir; 'APPROVED' gorunce kurulum tamamdir.")
    else:
        fail(f"Sablon onaylanmadi: {status} ({tpl.get('rejected_reason')}).\n"
             "   -> Bu sonucu Claude'a ilet; sablon metnini birlikte degistirelim.")


if __name__ == "__main__":
    main()
