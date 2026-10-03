"""
Default evidence folder templates for different investigation types.
These templates define the standard folder structures for organizing evidence.
"""


def _folder(name: str, description: str, *subfolders: dict) -> dict:
    return {"name": name, "description": description, "subfolders": list(subfolders)}


SOCIAL_MEDIA_SUBFOLDERS = [
    _folder("Bluesky", "Bluesky posts and profile evidence"),
    _folder("Discord", "Discord messages and server evidence"),
    _folder("Facebook", "Facebook posts and profile evidence"),
    _folder("Instagram", "Instagram posts and stories evidence"),
    _folder("LinkedIn", "LinkedIn profile and professional evidence"),
    _folder("Reddit", "Reddit posts and comment evidence"),
    _folder("Telegram", "Telegram messages and channel evidence"),
    _folder("TikTok", "TikTok videos and profile evidence"),
    _folder("Twitch", "Twitch streams and chat evidence"),
    _folder("X", "X (Twitter) posts and profile evidence"),
    _folder("YouTube", "YouTube videos and channel evidence"),
    _folder("Other", "Other social media platform evidence"),
]

ASSOCIATES_SUBFOLDERS = [
    _folder("Children", "Evidence related to children"),
    _folder("Colleagues", "Evidence related to work colleagues"),
    _folder("Father", "Evidence related to father"),
    _folder("Friends", "Evidence related to friends"),
    _folder("Mother", "Evidence related to mother"),
    _folder("Partner/Spouse", "Evidence related to partner or spouse"),
    _folder("Siblings", "Evidence related to siblings"),
    _folder("Other", "Evidence related to other associates"),
]

THREAT_INTEL_TEMPLATE = {
    "name": "Threat Intelligence",
    "description": "Folder structure for threat intelligence analysis",
    "folders": [
        _folder("Screenshots", "Screenshots and images from investigations"),
        _folder(
            "Network Logs",
            "Network traffic captures and log files",
            _folder("PCAP Files", "Network packet captures"),
            _folder("DNS Logs", "DNS query logs"),
            _folder("Firewall Logs", "Firewall and security logs"),
        ),
        _folder("Malware Samples", "Malware files and related artifacts"),
        _folder(
            "Analysis Reports",
            "Analysis reports and documentation",
            _folder("Sandbox Reports", "Automated analysis reports"),
            _folder("Manual Analysis", "Manual analysis documentation"),
        ),
        _folder("IOC Lists", "Indicator of compromise files and lists"),
        _folder("External Reports", "Third-party intelligence reports"),
    ],
}

COMPANY_TEMPLATE = {
    "name": "Company Investigation",
    "description": "Folder structure for corporate investigations",
    "folders": [
        _folder(
            "Executives",
            "Evidence related to company executives and leadership",
            _folder("CEO", "Evidence related to Chief Executive Officer"),
            _folder("CFO", "Evidence related to Chief Financial Officer"),
            _folder("CTO", "Evidence related to Chief Technology Officer"),
            _folder("CMO", "Evidence related to Chief Marketing Officer"),
            _folder("COO", "Evidence related to Chief Operating Officer"),
            _folder("Other", "Evidence related to other executives"),
        ),
        _folder(
            "Affiliates", "Evidence related to affiliated companies and relationships"
        ),
        _folder(
            "Social Media",
            "Company social media platform evidence",
            *SOCIAL_MEDIA_SUBFOLDERS,
        ),
        _folder("Network Assets", "Evidence related to network assets"),
    ],
}

PERSON_TEMPLATE = {
    "name": "Person Investigation",
    "description": "Folder structure for individual investigations",
    "folders": [
        _folder(
            "Social Media", "Social media platform evidence", *SOCIAL_MEDIA_SUBFOLDERS
        ),
        _folder(
            "Associates",
            "Evidence related to associates and relationships",
            *ASSOCIATES_SUBFOLDERS,
        ),
        _folder("Other", "Other evidence not categorized elsewhere"),
    ],
}

# Template registry
DEFAULT_TEMPLATES = {
    "ThreatIntel": THREAT_INTEL_TEMPLATE,
    "Company": COMPANY_TEMPLATE,
    "Person": PERSON_TEMPLATE,
}
