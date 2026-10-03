"""
Person investigation hunt definition
"""

from ..base_hunt import BaseHunt, HuntStepDefinition
from ..step_input_resolver import parse_input_expression


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

    def get_steps(self) -> list[HuntStepDefinition]:
        return [
            HuntStepDefinition(
                step_id="email_check",
                plugin_name="HolehePlugin",
                display_name="Check email usage",
                description="Find online accounts associated with the email address",
                parameter_mapping={"email": parse_input_expression("initial.email")},
            ),
        ]
