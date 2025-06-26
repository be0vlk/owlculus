"""
Person investigation hunt definition
"""

from typing import List

from ..base_hunt import BaseHunt, HuntStepDefinition


class PersonHunt(BaseHunt):
    """Comprehensive investigation of a person using email and name"""

    def __init__(self):
        super().__init__()
        self.display_name = "Person Deep Dive"
        self.description = "Comprehensive investigation of an individual using email address and optionally their name"
        self.category = "person"
        self.initial_parameters = {
            "email": {
                "type": "string",
                "description": "Email address to investigate",
                "required": True,
            },
            "full_name": {
                "type": "string",
                "description": "Full name of the person (optional)",
                "required": False,
            },
        }

    def get_steps(self) -> List[HuntStepDefinition]:
        return [
            HuntStepDefinition(
                step_id="email_check",
                plugin_name="HolehePlugin",
                display_name="Check email usage",
                description="Find online accounts associated with the email address",
                parameter_mapping={"email": "initial.email"},
            ),
            # Additional steps would be added here as plugins become available
            # For example:
            # HuntStepDefinition(
            #     step_id="breach_check",
            #     plugin_name="HIBPPlugin",
            #     display_name="Check data breaches",
            #     description="Search for email in known data breaches",
            #     parameter_mapping={
            #         "email": "initial.email"
            #     },
            #     optional=True
            # ),
            # HuntStepDefinition(
            #     step_id="social_search",
            #     plugin_name="SocialSearchPlugin",
            #     display_name="Social media search",
            #     description="Search for profiles on social platforms",
            #     parameter_mapping={
            #         "query": "initial.full_name",
            #         "email_hint": "initial.email"
            #     },
            #     depends_on=["email_check"],
            #     optional=True
            # )
        ]
