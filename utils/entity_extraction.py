import re
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_entities(text):
    doc = nlp(text)

    phones = re.findall(r'\b\d{10}\b', text)
    emails = re.findall(r'\S+@\S+', text)

    names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]

    return {
        "phones": list(set(phones)),
        "emails": list(set(emails)),
        "persons": list(set(names)),
        "organizations": list(set(orgs))
    }
