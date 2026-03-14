import requests
import re
import urllib.parse

def search_company_links(company_name, job_text=""):
    """
    Returns official website using DuckDuckGo API and LinkedIn using direct search
    Also extracts website URLs from job description if present
    """
    if not company_name or len(company_name.strip()) < 3:
        return {"company": company_name, "website": None, "linkedin": None}
    
    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', company_name).strip()
    
    website = extract_website_from_text(job_text)
    
    if not website:
        website = search_official_website(clean_name)
    
    # Search for LinkedIn using direct link construction
    linkedin = search_linkedin_page(clean_name)
    
    return {
        "company": company_name,
        "website": website,
        "linkedin": linkedin
    }

def extract_website_from_text(text):
    """Extract website URLs from job description text"""
    if not text:
        return None
    
    # URL patterns to match
    url_patterns = [
        r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)',
        r'www\.([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)',
        r'(?:visit|website|site)\s*:?\s*((?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
    ]
    
    skip_domains = ["indeed", "glassdoor", "naukri", "monster", "linkedin"]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            url = match if match.startswith('http') else f"https://{match}"
            if not any(domain in url.lower() for domain in skip_domains):
                return url
    
    return None

def search_official_website(company_name):
    """Search for official website using multiple methods"""
    # Method 1: Try common domain patterns first (most reliable)
    common_domains = generate_common_domains(company_name)
    for domain in common_domains:
        if check_website_exists(domain):
            return domain
    
    # Method 2: Use SerpAPI alternative - construct search URL for user to visit
    search_query = f"{company_name} official website"
    google_search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
    
    # Since we can't get actual search results without API keys, return the search URL
    # This allows users to click and find the official website themselves
    return google_search_url

def generate_common_domains(company_name):
    """Generate common domain patterns for a company"""
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
    clean_name = clean_name.replace('inc', '').replace('llc', '').replace('corp', '').replace('ltd', '')
    
    domains = []
    if len(clean_name) > 2:
        domains.extend([
            f"https://www.{clean_name}.com",
            f"https://{clean_name}.com",
            f"https://www.{clean_name}.org",
            f"https://www.{clean_name}.net"
        ])
    
    # Try with spaces as hyphens
    hyphen_name = company_name.lower().replace(' ', '-')
    hyphen_name = re.sub(r'[^a-zA-Z0-9-]', '', hyphen_name)
    if len(hyphen_name) > 2:
        domains.extend([
            f"https://www.{hyphen_name}.com",
            f"https://{hyphen_name}.com"
        ])
    
    return domains

def check_website_exists(url):
    """Check if a website exists and is accessible"""
    try:
        response = requests.head(url, timeout=3, allow_redirects=True)
        return response.status_code < 400
    except:
        return False

def is_valid_company_url(url, company_name):
    """Check if URL is a valid company website"""
    skip_domains = ["wikipedia", "indeed", "glassdoor", "naukri", "monster", "linkedin", "facebook", "twitter", "youtube"]
    return url.startswith('http') and not any(domain in url.lower() for domain in skip_domains)

def search_linkedin_page(company_name):
    """Search for LinkedIn page using search keywords URL"""
    # Create LinkedIn search URL with keywords
    search_keywords = company_name.replace(' ', '%20')
    linkedin_search_url = f"https://www.linkedin.com/search/results/companies/?keywords={search_keywords}"
    
    return linkedin_search_url