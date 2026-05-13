"""
outreach.py — Outreach Email Generator
Generates personalized cold emails for qualified leads.
"""

import os
import json
import re
import logging
from anthropic import Anthropic
from typing import Dict

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def generate_outreach_email(lead: Dict, preview: Dict) -> Dict:
    """
    Generate a personalized outreach email as a structured JSON object.
    """
    contact_name = lead.get('contact_name', f"the {lead.get('name')} team")

    prompt = f"""
You are an expert B2B sales development representative for WebPulse, a top-tier web design agency.
Your task is to write a compelling, personalized, and concise cold email to a potential client.

**Client Information:**
- Business Name: {lead['name']}
- Website: {lead['website']}
- Industry: {lead['category']}
- Location: {lead['city']}, {lead['state']}
- Identified Issues with Current Site: {', '.join(lead.get('improvement_suggestions', ['N/A']))}
- Proposed High-Level Improvements: {', '.join(preview.get('key_improvements', ['N/A']))}

**Email Generation Rules:**
1.  **Subject Line:** Create a short, intriguing subject line. It should be personalized to the business, not a generic "Website Redesign" template. Mention their business name or city.
2.  **Salutation:** Address it to "{contact_name}".
3.  **Opening:** Start with a personalized observation about their business or website. Show you've done some research.
4.  **Value Proposition:** Briefly state that you've identified opportunities for improvement (e.g., modern design, mobile experience, branding). Connect these to business outcomes like attracting more customers.
5.  **The "Hook":** Mention that you've prepared a complimentary, no-obligation redesign concept to visualize the potential. Assume this is available at a placeholder link `[PREVIEW_LINK]`.
6.  **Call to Action (CTA):** Keep it low-friction. Ask if they are the right person to discuss this with, or if they'd be open to seeing the preview.
7.  **Closing:** A professional closing (e.g., "Best regards,").
8.  **Format:** Return a single JSON object with two keys: "subject" and "body". Do not include any other text or markdown.

**Example JSON Output:**
{{
  "subject": "A thought on the WebPulse website",
  "body": "Hi team,\\n\\nI was just looking at your site... and had an idea..."
}}

Generate the JSON for {lead['name']} now.
"""

    try:
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
        # Basic JSON extraction
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            logger.warning(f"Could not parse JSON from outreach model for {lead['name']}. Using raw text for body.")
            return {"subject": f"A quick question about {lead['name']}", "body": response_text}
    except Exception as e:
        logger.error(f"Error generating email for {lead['name']}: {e}")
        return {"subject": "Error", "body": f"Error generating email: {e}"}