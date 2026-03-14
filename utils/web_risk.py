import re

SUSPICIOUS_KEYWORDS = [
    "registration fee",
    "processing fee",
    "training fee",
    "payment required",
    "pay to apply",
    "security deposit",
    "earn per day",
    "work from home and earn",
    "limited slots",
    "immediate joining",
    "no interview",
    "no experience required",
    "whatsapp only",
    "contact immediately",
    "urgent hiring",
    "guaranteed job",
    "100% placement"
]

FREE_EMAIL_DOMAINS = [
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "protonmail.com"
]

PHONE_REGEX = r"\+?\d[\d\s\-]{8,}"

def calculate_web_risk(text):
    text = text.lower()
    risk_score = 0
    matches = []

    # 1️⃣ Suspicious keyword detection
    keyword_hits = []
    for kw in SUSPICIOUS_KEYWORDS:
        if kw in text:
            keyword_hits.append(kw)

    if keyword_hits:
        risk_score += min(0.4, 0.05 * len(keyword_hits))
        matches.append(
            f"Suspicious phrases detected: {', '.join(keyword_hits[:3])}"
        )

    # 2️⃣ Money request detection
    if re.search(r"(pay|payment|fee|deposit).*(job|training|register)", text):
        risk_score += 0.3
        matches.append("Mentions payment or fees related to job")

    # 3️⃣ Urgency manipulation
    urgency_words = ["urgent", "immediate", "asap", "limited time"]
    if any(word in text for word in urgency_words):
        risk_score += 0.15
        matches.append("Uses urgency or pressure tactics")

    # 4️⃣ Phone-only contact
    if re.search(PHONE_REGEX, text) and "@" not in text:
        risk_score += 0.2
        matches.append("Only phone number provided, no official email")

    # 5️⃣ Free email domain detection
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    for email in emails:
        domain = email.split("@")[-1]
        if domain in FREE_EMAIL_DOMAINS:
            risk_score += 0.2
            matches.append(f"Uses free email domain: {domain}")
            break

    # Cap risk score
    risk_score = min(risk_score, 1.0)

    return risk_score, matches
