from pydantic import BaseModel
class Job(BaseModel):
    title: str
    company: str
    experience: str
    location: str
    job_desc: str
    skills: list[str]

BASE_URL = 'https://www.naukri.com/it-jobs'
#CSS_SELECTOR = '[class^="srp-jobtuple-wrapper"]'
CSS_SELECTOR = '[class^="styles_middle-section-container"]'
REQUIRED_KEYS = [
    'title',
    'company',
    'experience',
    'job-desc',
    'skills'
]

