"""
Resume field extraction service.
Extracts structured data (experience, education, certifications, etc.) from resume text.
"""
import re
from app.core.logger import get_logger

logger = get_logger("field_extractor")


def extract_name(text: str) -> str | None:
    """
    Try to extract candidate name from first line or email-like patterns.
    Returns the first meaningful line that looks like a name.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Skip common header lines
    skip_patterns = [r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', r'^(?:\+|)[0-9\s\-()]+$', r'^\d+']
    
    for line in lines[:10]:  # Check first 10 lines
        if not any(re.match(pattern, line) for pattern in skip_patterns):
            # If it's a reasonable name (not too long, no URLs)
            if len(line) < 100 and 'http' not in line.lower() and '/' not in line:
                return line.replace('_', ' ').title()
    
    return None


def extract_email(text: str) -> str | None:
    """Extract email address from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    """Extract phone number from text."""
    # Support international formats: +91 9876543210, (91) 9876543210, 9876543210, etc.
    pattern = r'(?:\+|Country code:?\s*)?\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}'
    match = re.search(pattern, text)
    if match:
        phone = match.group(0).strip()
        # Filter out unlikely matches
        if len(re.findall(r'\d', phone)) >= 10:
            return phone
    return None


def extract_location(text: str) -> str | None:
    """
    Extract location from text.
    Look for patterns like "Location:", "Based in:", "City, State" format.
    """
    # Common location indicators
    location_patterns = [
        r'(?:Location|Based in|City|Address)[:\s]+([A-Za-z\s,.-]+?)(?:\n|$|[,.])',
        r'(?:^|,\s)([A-Za-z\s]+?),\s*(?:India|USA|UK|CA|AU)(?:\n|$|,)',
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            if location and len(location) < 100:
                return location
    
    return None


def extract_experience(text: str) -> list[dict]:
    """
    Extract work experience entries from resume text.
    Looks for patterns like "Company | Title | Duration" or "Company - Title (start - end)"
    """
    experience = []
    
    # Patterns for experience sections
    exp_patterns = [
        # "Company | Title | start-end"
        r'([A-Za-z\s&.,]+?)\s*\|\s*([A-Za-z\s]+?)\s*\|\s*([\w\s\-/,]+)',
        # "Company - Title (start-end)"
        r'([A-Za-z\s&.,]+?)\s*[-–]\s*([A-Za-z\s]+?)\s*\(([\w\s\-/,]+)\)',
        # "Title at Company (start - end)"
        r'([A-Za-z\s]+?)\s+at\s+([A-Za-z\s&.,]+?)\s*\(([\w\s\-/,]+)\)',
    ]
    
    text_lower = text.lower()
    
    # Find experience section
    exp_section_match = re.search(r'(?:work\s+)?experience[:\n]+(.+?)(?:education|certification|language|project|$)', text, re.IGNORECASE | re.DOTALL)
    if exp_section_match:
        exp_text = exp_section_match.group(1)
    else:
        exp_text = text
    
    # Extract entries
    for pattern in exp_patterns:
        matches = re.finditer(pattern, exp_text, re.IGNORECASE)
        for match in matches:
            try:
                title, company, duration = match.groups()
                title = title.strip()
                company = company.strip()
                duration = duration.strip()
                
                # Validate
                if len(title) > 3 and len(company) > 3 and len(duration) > 3:
                    experience.append({
                        "company": company.title(),
                        "title": title.title(),
                        "duration": duration,
                        "startDate": _extract_date(duration),
                        "endDate": _extract_end_date(duration),
                        "current": "current" in duration.lower() or "present" in duration.lower(),
                        "description": None,
                    })
            except (IndexError, AttributeError):
                continue
    
    return experience[:10]  # Limit to 10 entries


def extract_education(text: str) -> list[dict]:
    """
    Extract education entries from resume.
    Looks for patterns like "B.Tech | University | 2020" or "Degree - Institution"
    """
    education = []
    
    # Find education section
    edu_section_match = re.search(r'education[:\n]+(.+?)(?:experience|certification|language|project|skill|$)', text, re.IGNORECASE | re.DOTALL)
    if edu_section_match:
        edu_text = edu_section_match.group(1)
    else:
        edu_text = text
    
    # Common degree patterns
    degree_keywords = [
        r'(?:B\.?Tech|Bachelor of Technology|Bachelor of Science|B\.?Sc)',
        r'(?:M\.?Tech|Master of Technology|Master of Science|M\.?Sc)',
        r'(?:BCA|MCA|Bachelor of Computer Applications|Master of Computer Applications)',
        r'(?:B\.?A|Bachelor of Arts)',
        r'(?:B\.?E|Bachelor of Engineering)',
        r'(?:MBA|Master of Business Administration)',
        r'(?:PhD|Doctor of Philosophy)',
    ]
    
    # Extract entries
    lines = [line.strip() for line in edu_text.split('\n') if line.strip()]
    for i, line in enumerate(lines):
        for degree_pattern in degree_keywords:
            if re.search(degree_pattern, line, re.IGNORECASE):
                # Extract degree
                degree = re.search(degree_pattern, line, re.IGNORECASE).group(0)
                
                # Try to find institution and year
                institution = None
                year = None
                
                # Institution might be in same line or next line
                parts = re.split(r'[|,\-]', line)
                for part in parts:
                    part = part.strip()
                    if 'university' in part.lower() or 'institute' in part.lower() or 'college' in part.lower():
                        institution = part.replace('University', '').replace('Institute', '').replace('College', '').strip()
                        break
                    elif len(part) > 10 and part not in degree:
                        institution = part
                
                # Extract year
                year_match = re.search(r'20\d{2}', line)
                if year_match:
                    year = int(year_match.group(0))
                
                if degree:
                    education.append({
                        "degree": degree.title(),
                        "institution": institution or "Unknown",
                        "field": _extract_field(line),
                        "startYear": year - 4 if year else None,
                        "endYear": year,
                        "gpa": _extract_gpa(line),
                    })
                break
    
    return education[:5]  # Limit to 5 entries


def extract_certifications(text: str) -> list[str]:
    """Extract certifications from resume text."""
    certifications = []
    
    # Find certification section
    cert_section_match = re.search(r'(?:certification|certified|credential|license)[s]?[:\n]+(.+?)(?:education|experience|language|project|skill|$)', text, re.IGNORECASE | re.DOTALL)
    if cert_section_match:
        cert_text = cert_section_match.group(1)
    else:
        cert_text = text
    
    # Common certification patterns
    cert_patterns = [
        r'(?:AWS|Azure|Google Cloud|GCP)\s+(?:Certified\s+)?([A-Za-z\s&.,-]+?)(?:\n|$|,)',
        r'(?:Certified|CISWA|PMP|SCRUM|CCNA|CCNP)\s+([A-Za-z\s&.,-]+?)(?:\n|$|,)',
        r'([A-Za-z0-9\s&.,-]+?)\s+(?:Certification|Certificate)(?:\n|$|,)',
    ]
    
    for pattern in cert_patterns:
        matches = re.finditer(pattern, cert_text, re.IGNORECASE)
        for match in matches:
            try:
                cert = match.group(1).strip()
                if len(cert) > 3 and len(cert) < 200 and cert not in certifications:
                    certifications.append(cert.title())
            except (IndexError, AttributeError):
                continue
    
    return certifications[:10]  # Limit to 10 certifications


def extract_languages(text: str) -> list[str]:
    """Extract languages from resume text."""
    languages = []
    
    # Find language section
    lang_section_match = re.search(r'language[s]?[:\n]+(.+?)(?:certification|education|experience|project|skill|$)', text, re.IGNORECASE | re.DOTALL)
    if lang_section_match:
        lang_text = lang_section_match.group(1)
    else:
        lang_text = text
    
    # Common programming and natural languages
    all_languages = [
        # Programming languages
        'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Rust',
        'Scala', 'Kotlin', 'Swift', 'R', 'Matlab', 'SQL', 'Bash', 'Ruby', 'PHP',
        'Perl', 'Groovy', 'Haskell', 'Elixir', 'Clojure', 'F#',
        # Natural languages
        'English', 'Hindi', 'Spanish', 'French', 'German', 'Chinese', 'Japanese',
        'Korean', 'Portuguese', 'Italian', 'Dutch', 'Russian', 'Arabic', 'Bengali',
        'Punjabi', 'Telugu', 'Marathi', 'Tamil', 'Gujarati', 'Urdu', 'Polish',
    ]
    
    for lang in all_languages:
        if re.search(r'\b' + lang + r'\b', lang_text, re.IGNORECASE):
            if lang not in languages:
                languages.append(lang)
    
    return languages[:15]  # Limit to 15 languages


def extract_total_experience_years(text: str) -> float | None:
    """
    Extract total years of experience from resume text.
    Looks for patterns like "X years of experience", "X+ years", etc.
    """
    pattern = r'(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp|work)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # Alternative: count from experience entries
    exp_dates = re.findall(r'20\d{2}', text)
    if len(exp_dates) >= 2:
        try:
            start = min(int(d) for d in exp_dates)
            end = max(int(d) for d in exp_dates)
            years = end - start
            if 0 < years <= 60:  # Reasonable range
                return float(years)
        except (ValueError, TypeError):
            pass
    
    return None


# ── Helper functions ──────────────────────────────────────────────────────────

def _extract_date(duration: str) -> str | None:
    """Extract start date from duration string like 'Jan 2020 - Dec 2022'."""
    pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]?\s+20\d{2}'
    match = re.search(pattern, duration, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_end_date(duration: str) -> str | None:
    """Extract end date from duration string."""
    pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]?\s+20\d{2}'
    matches = re.findall(pattern, duration, re.IGNORECASE)
    return matches[-1] if len(matches) > 1 else None


def _extract_field(line: str) -> str:
    """Extract field of study from education line."""
    field_keywords = [
        'Computer Science', 'Computer Engineering', 'Software Engineering',
        'Artificial Intelligence', 'Machine Learning', 'Data Science',
        'Electronics', 'Electrical', 'Mechanical', 'Civil', 'Information Technology',
        'Business Administration', 'Economics', 'Mathematics', 'Physics', 'Chemistry',
    ]
    
    for field in field_keywords:
        if field.lower() in line.lower():
            return field
    
    # Default field extraction
    parts = re.split(r'[|,\-]', line)
    for part in parts:
        part = part.strip()
        if 'degree' not in part.lower() and len(part) > 5 and len(part) < 100:
            return part.title()
    
    return "General"


def _extract_gpa(line: str) -> float | None:
    """Extract GPA from line if present."""
    pattern = r'(?:GPA|CGPA)[:\s]*(\d+\.\d{1,2})'
    match = re.search(pattern, line, re.IGNORECASE)
    if match:
        try:
            gpa = float(match.group(1))
            if 0 < gpa <= 4.0:
                return gpa
        except ValueError:
            pass
    return None


def extract_all_fields(text: str) -> dict:
    """
    Extract all resume fields and return as a structured dict.
    This is the main entry point for field extraction.
    """
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "location": extract_location(text),
        "summary": None,
        "skills": [],  # Handled separately by skill_extractor
        "experience": extract_experience(text),
        "education": extract_education(text),
        "certifications": extract_certifications(text),
        "languages": extract_languages(text),
        "totalExperienceYears": extract_total_experience_years(text),
    }
