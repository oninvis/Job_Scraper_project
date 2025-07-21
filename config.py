from pydantic import BaseModel
class Job(BaseModel):
    title: str
    company: str
    experience: str
    location: str
    job_desc: str
    skills: list[str]

BASE_URL = 'https://www.naukri.com/it-jobs' # change the base url as per your requirement
CSS_SELECTOR = '[class^=srp-jobtuple-wrapper]' # change the css selector according to the website structure
REQUIRED_KEYS = [
    'title',
    'company',
    'experience',
    'job-description',
    'skills'
]


