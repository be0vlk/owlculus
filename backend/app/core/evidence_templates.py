"""
Default evidence folder templates for different investigation types.
These templates define the standard folder structures for organizing evidence.
"""

SOCIAL_MEDIA_SUBFOLDERS = [
    {
        "name": "Bluesky",
        "description": "Bluesky posts and profile evidence",
        "subfolders": [],
    },
    {
        "name": "Discord",
        "description": "Discord messages and server evidence",
        "subfolders": [],
    },
    {
        "name": "Facebook",
        "description": "Facebook posts and profile evidence",
        "subfolders": [],
    },
    {
        "name": "Instagram",
        "description": "Instagram posts and stories evidence",
        "subfolders": [],
    },
    {
        "name": "LinkedIn",
        "description": "LinkedIn profile and professional evidence",
        "subfolders": [],
    },
    {
        "name": "Reddit",
        "description": "Reddit posts and comment evidence",
        "subfolders": [],
    },
    {
        "name": "Telegram",
        "description": "Telegram messages and channel evidence",
        "subfolders": [],
    },
    {
        "name": "TikTok",
        "description": "TikTok videos and profile evidence",
        "subfolders": [],
    },
    {
        "name": "Twitch",
        "description": "Twitch streams and chat evidence",
        "subfolders": [],
    },
    {
        "name": "X",
        "description": "X (Twitter) posts and profile evidence",
        "subfolders": [],
    },
    {
        "name": "YouTube",
        "description": "YouTube videos and channel evidence",
        "subfolders": [],
    },
    {
        "name": "Other",
        "description": "Other social media platform evidence",
        "subfolders": [],
    },
]

ASSOCIATES_SUBFOLDERS = [
    {
        "name": "Children",
        "description": "Evidence related to children",
        "subfolders": [],
    },
    {
        "name": "Colleagues",
        "description": "Evidence related to work colleagues",
        "subfolders": [],
    },
    {"name": "Father", "description": "Evidence related to father", "subfolders": []},
    {"name": "Friends", "description": "Evidence related to friends", "subfolders": []},
    {"name": "Mother", "description": "Evidence related to mother", "subfolders": []},
    {
        "name": "Partner/Spouse",
        "description": "Evidence related to partner or spouse",
        "subfolders": [],
    },
    {
        "name": "Siblings",
        "description": "Evidence related to siblings",
        "subfolders": [],
    },
    {
        "name": "Other",
        "description": "Evidence related to other associates",
        "subfolders": [],
    },
]

PERSON_SUBFOLDERS = [
    {
        "name": "Social Media",
        "description": "Social media platform evidence",
        "subfolders": SOCIAL_MEDIA_SUBFOLDERS.copy(),
    },
    {
        "name": "Associates",
        "description": "Evidence related to associates and relationships",
        "subfolders": ASSOCIATES_SUBFOLDERS.copy(),
    },
    {
        "name": "Other",
        "description": "Other evidence not categorized elsewhere",
        "subfolders": [],
    },
]

THREAT_INTEL_TEMPLATE = {
    "name": "Threat Intelligence",
    "description": "Folder structure for threat intelligence analysis",
    "folders": [
        {
            "name": "Screenshots",
            "description": "Screenshots and images from investigations",
            "subfolders": [],
        },
        {
            "name": "Network Logs",
            "description": "Network traffic captures and log files",
            "subfolders": [
                {
                    "name": "PCAP Files",
                    "description": "Network packet captures",
                    "subfolders": [],
                },
                {"name": "DNS Logs", "description": "DNS query logs", "subfolders": []},
                {
                    "name": "Firewall Logs",
                    "description": "Firewall and security logs",
                    "subfolders": [],
                },
            ],
        },
        {
            "name": "Malware Samples",
            "description": "Malware files and related artifacts",
            "subfolders": [],
        },
        {
            "name": "Analysis Reports",
            "description": "Analysis reports and documentation",
            "subfolders": [
                {
                    "name": "Sandbox Reports",
                    "description": "Automated analysis reports",
                    "subfolders": [],
                },
                {
                    "name": "Manual Analysis",
                    "description": "Manual analysis documentation",
                    "subfolders": [],
                },
            ],
        },
        {
            "name": "IOC Lists",
            "description": "Indicator of compromise files and lists",
            "subfolders": [],
        },
        {
            "name": "External Reports",
            "description": "Third-party intelligence reports",
            "subfolders": [],
        },
    ],
}

COMPANY_TEMPLATE = {
    "name": "Company Investigation",
    "description": "Folder structure for corporate investigations",
    "folders": [
        {
            "name": "Executives",
            "description": "Evidence related to company executives and leadership",
            "subfolders": [
                {
                    "name": "CEO",
                    "description": "Evidence related to Chief Executive Officer",
                    "subfolders": [],
                },
                {
                    "name": "CFO",
                    "description": "Evidence related to Chief Financial Officer",
                    "subfolders": [],
                },
                {
                    "name": "CTO",
                    "description": "Evidence related to Chief Technology Officer",
                    "subfolders": [],
                },
                {
                    "name": "CMO",
                    "description": "Evidence related to Chief Marketing Officer",
                    "subfolders": [],
                },
                {
                    "name": "COO",
                    "description": "Evidence related to Chief Operating Officer",
                    "subfolders": [],
                },
                {
                    "name": "Other",
                    "description": "Evidence related to other executives",
                    "subfolders": [],
                },
            ],
        },
        {
            "name": "Affiliates",
            "description": "Evidence related to affiliated companies and relationships",
            "subfolders": [],
        },
        {
            "name": "Social Media",
            "description": "Company social media platform evidence",
            "subfolders": SOCIAL_MEDIA_SUBFOLDERS.copy(),
        },
        {
            "name": "Network Assets",
            "description": "Evidence related to network assets",
            "subfolders": [],
        },
    ],
}

PERSON_TEMPLATE = {
    "name": "Person Investigation",
    "description": "Folder structure for individual investigations",
    "folders": PERSON_SUBFOLDERS.copy(),
}

# Template registry
DEFAULT_TEMPLATES = {
    "ThreatIntel": THREAT_INTEL_TEMPLATE,
    "Company": COMPANY_TEMPLATE,
    "Person": PERSON_TEMPLATE,
}
