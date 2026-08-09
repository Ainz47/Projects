"""
config.py — Deployment configuration model.
Validated once at the start of every deploy run.
"""
from dataclasses import dataclass, field
from typing import List


DEFAULT_SERVICES = [
    "Concrete Driveways",
    "Stamped Concrete Patios",
    "Concrete Walkways",
    "Concrete Repair",
    "Concrete Paving",
    "Concrete Foundations",
]

DEFAULT_BLOG_TOPICS = [
    "How to Choose the Right Concrete Contractor",
    "Stamped Concrete vs. Pavers: Which Is Better?",
    "When to Repair vs. Replace Your Concrete Driveway",
]


@dataclass
class DeployConfig:
    # Target WordPress site
    wp_url: str           # e.g. https://mysite.com
    wp_username: str
    wp_password: str      # WP admin login password (used for cookie auth)

    # Business identity
    business_name: str    # e.g. Elite Plumbing Detroit
    city: str             # e.g. Detroit
    state: str            # e.g. MI
    phone: str            # e.g. (313) 555-0100

    # Design
    primary_color: str    # e.g. #ff5e14
    dark_color: str = "#1a1a1a"

    # Fully custom — user enters whatever they want
    services: List[str] = field(default_factory=lambda: list(DEFAULT_SERVICES))
    blog_topics: List[str] = field(default_factory=lambda: list(DEFAULT_BLOG_TOPICS))

    # API keys (read from env if empty)
    gemini_api_key: str = ""
    pexels_api_key: str = ""

    # Optional Google Maps embed URL (from Google Maps → Share → Embed a map)
    maps_embed_url: str = ""

    # Optional rich 3-column footer (business name, services, contact)
    rich_footer: bool = False

    # Email address that receives contact form submissions
    contact_email: str = ""

    # SMTP — if provided, WP Mail SMTP is installed and configured automatically
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_encryption: str = "tls"   # tls | ssl | none
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_name: str = ""
    smtp_from_email: str = ""

    def wp_api_base(self) -> str:
        return self.wp_url.rstrip("/") + "/wp-json/wp/v2"

    def wp_site_url(self) -> str:
        return self.wp_url.rstrip("/")

    def validate(self) -> list:
        errors = []
        if not self.wp_url.startswith("http"):
            errors.append("WP URL must start with http:// or https://")
        if not self.wp_username:
            errors.append("WP username is required")
        if not self.wp_password:
            errors.append("WP password is required")
        if not self.business_name:
            errors.append("Business name is required")
        if not self.city:
            errors.append("City is required")
        if not self.state:
            errors.append("State is required")
        if not self.phone:
            errors.append("Phone is required")
        if not self.primary_color.startswith("#"):
            errors.append("Primary color must be a hex code (e.g. #ff5e14)")
        if not self.services:
            errors.append("At least one service must be selected")
        return errors
