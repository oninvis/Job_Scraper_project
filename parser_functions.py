from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import csv
import json
from config import CSS_SELECTOR_indeed_dir_page , CSS_SELECTOR_naukri_dir_page, CSS_SELECTOR_indeed, CSS_SELECTOR_naukri

def user_params(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
    job_number: int = 10,
):
    return company, location, profession, website_name, job_number


def text_or(el, default=""):
    return el.get_text(strip=True) if el else default


def parse_posted_date(rel: str):
    """
    Convert strings like '1 day ago', '3 weeks ago', 'Just now',
    or 'Starts in 1-3 months' into a datetime.date.
    Returns None if it can’t parse.

    """
    rel = rel.lower().strip()
    today = datetime.today()

    if not rel:
        return None
    if "just now" in rel:
        return today.date()

    # X days ago
    m = re.match(r"(\d+)\s*day", rel)
    if m:
        return (today - timedelta(days=int(m.group(1)))).date()

    # X weeks ago
    m = re.match(r"(\d+)\s*week", rel)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).date()

    # X months ago (approximate as 30 days each)
    m = re.match(r"(\d+)\s*month", rel)
    if m:
        return (today - timedelta(days=30 * int(m.group(1)))).date()

    # Starts in X days / weeks / months
    m = re.match(r"starts in\s*(\d+)\s*day", rel)
    if m:
        return (today + timedelta(days=int(m.group(1)))).date()
    m = re.match(r"starts in\s*(\d+)\s*week", rel)
    if m:
        return (today + timedelta(weeks=int(m.group(1)))).date()
    m = re.match(r"starts in\s*(\d+)\s*month", rel)
    if m:
        return (today + timedelta(days=30 * int(m.group(1)))).date()

    return None


def change_base_url(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
):
    if website_name == "naukri":
        input_url = "https://www.naukri.com"
        if company and location and profession:
            BASE_URL = f"{input_url}/{profession}-{company}-jobs-in-{location}"
        elif company and profession:
            BASE_URL = f"{input_url}/{company}-{profession}-jobs"
        elif location and profession:
            BASE_URL = f"{input_url}/jobs-in-{location}-{profession}"
        elif company and location:
            BASE_URL = f"{input_url}/{company}-jobs-in-{location}"
        elif company:
            BASE_URL = f"{input_url}/{company}-jobs"
        elif location:
            BASE_URL = f"{input_url}/jobs-in-{location}"
        elif profession:
            BASE_URL = f"{input_url}/{profession}-jobs"
        else:
            BASE_URL = input_url
        return BASE_URL , input_url
    elif website_name == "indeed":
        input_url = "https://www.indeed.com"
        if company and location and profession:
            BASE_URL = f"{input_url}/jobs?q={profession}+{company}&l={location}"
        elif company and profession:
            BASE_URL = f"{input_url}/jobs?q={company}+{profession}"
        elif location and profession:
            BASE_URL = f"{input_url}/jobs?q={profession}&l={location}"
        elif company and location:
            BASE_URL = f"{input_url}/jobs?q={company}&l={location}"
        elif company:
            BASE_URL = f"{input_url}/jobs?q={company}"
        elif location:
            BASE_URL = f"{input_url}/jobs?l={location}"
        elif profession:
            BASE_URL = f"{input_url}/jobs?q={profession}"
        else:
            BASE_URL = input_url
        return BASE_URL , input_url
    else:
        return None



def get_parsed_jobs_naukri(result, jobs):
    """Parses a Naukri detail‐page (CSS_SELECTOR_naukri_dir_page → div[class*='jd-container'])."""
    soup = BeautifulSoup(result.html, "html.parser")
    # the container whose class contains “jd-container”
    container = soup.select_one("div[class*='jd-container']")
    if not container:
        return  # nothing to do

    # TITLE
    title_el = container.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # COMPANY
    comp_el = container.select_one("div[class*='jd-header-comp-name'] a")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # EXPERIENCE & LOCATION live in the same metadata block
    experience = ""
    location = ""
    for li in container.select("div[class*='jd-header-meta'] li"):
        txt = li.get_text(" ", strip=True)
        if "Experience" in txt:
            experience = txt
        elif "Location" in txt:
            location = txt

    # POSTED DATE
    posted_el = container.select_one("div[class*='other-details'] span")
    posted = posted_el.get_text(strip=True) if posted_el else ""

    # DESCRIPTION
    desc_el = soup.select_one("#jdJobDescMain")
    description = desc_el.get_text(" ", strip=True) if desc_el else ""

    # SKILLS (key skills tags)
    skills = [li.get_text(strip=True) for li in soup.select("ul.key-skill-tags li")]

    jobs.append({
        "title":       title,
        "company":     company,
        "experience":  experience,
        "location":    location,
        "posted":      posted,
        "description": description,
        "skills":      skills,
    })


def get_parsed_jobs_indeed(result, jobs):
    """Parses an Indeed detail‐page (CSS_SELECTOR_indeed_dir_page → div.jobsearch-JobComponent)."""
    soup = BeautifulSoup(result.html, "html.parser")
    container = soup.select_one("div.jobsearch-JobComponent")
    if not container:
        return

    # TITLE
    title_el = container.select_one("h1.jobsearch-JobInfoHeader-title")
    title = title_el.get_text(strip=True) if title_el else ""

    # COMPANY
    comp_el = container.select_one("div.jobsearch-InlineCompanyRating div")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # LOCATION
    loc_el = container.select_one("div.jobsearch-JobInfoHeader-subtitle div:last-of-type")
    location = loc_el.get_text(strip=True) if loc_el else ""

    # POSTED DATE (often in the metadata footer)
    posted = ""
    footer = container.select_one("div.jobsearch-JobMetadataFooter")
    if footer:
        # the last <span> in that footer is usually the “X days ago”
        spans = footer.select("span")
        if spans:
            posted = spans[-1].get_text(strip=True)

    # DESCRIPTION
    desc_el = container.select_one("#jobDescriptionText")
    description = desc_el.get_text(" ", strip=True) if desc_el else ""

    # BENEFITS (if you’d still like to capture them)
    benefits = [li.get_text(strip=True)
                for li in container.select("ul.jobsearch-JobDescriptionSection-sectionItem ul li")]

    jobs.append({
        "title":       title,
        "company":     company,
        "location":    location,
        "posted":      posted,
        "description": description,
        "benefits":    benefits,
    })



def convert_to_csv(jobs, filename="jobs.csv"):
    if not jobs:
        print("No jobs to save.")
        return

    # Dynamically infer the exact columns from the first job dict
    field_names = list(jobs[0].keys())

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Extracted {len(jobs)} jobs and saved to {filename}")

