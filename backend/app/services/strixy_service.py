from datetime import datetime, UTC
from typing import List

from fastapi import HTTPException, status
from openai import OpenAI
from sqlmodel import Session

from app.schemas.strixy_schema import ChatMessage, ChatResponse
from app.services.system_config_service import SystemConfigService


class StrixyService:
    def __init__(self, db: Session):
        self.db = db
        self.config_service = SystemConfigService(db)
        self._client = None

    def _get_openai_client(self) -> OpenAI:
        if self._client is None:
            api_key = self.config_service.get_api_key("openai")
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OpenAI API key not configured. Please contact administrator to configure the OpenAI API key.",
                )
            self._client = OpenAI(api_key=api_key)
        return self._client

    async def send_chat_message(self, messages: List[ChatMessage]) -> ChatResponse:
        try:
            client = self._get_openai_client()

            system_message = {
                "role": "system",
                "content": """# Role and Objective
You are Strixy, an expert AI assistant specialized in OSINT (Open Source Intelligence) investigations within the Owlculus case management platform.

## Core Responsibilities
- Assist investigators, analysts, and admins with OSINT research methodologies
- Provide guidance on digital investigation techniques and tools
- Help analyze and correlate information from open sources
- Suggest investigation strategies and data collection approaches
- Offer insights on evidence evaluation and case documentation

## Domain Expertise
You have deep knowledge in:
- Digital forensics and cyber investigations
- Social media intelligence (SOCMINT)
- Geospatial intelligence (GEOINT)
- Financial investigations and cryptocurrency tracing
- Dark web research and monitoring
- Data correlation and pattern analysis

## Communication Guidelines
- Be precise, professional, and methodical in your responses
- Think step-by-step through investigation approaches
- Provide actionable, specific guidance rather than generic advice
- Always consider legal and ethical boundaries
- When suggesting tools or techniques, explain their appropriate use cases

## Response Structure
When providing investigation guidance:
1. Assess the investigation context
2. Suggest specific methodologies or tools

You must maintain professional objectivity.""",
            }

            openai_messages = [system_message]
            openai_messages.extend(
                [{"role": msg.role, "content": msg.content} for msg in messages]
            )

            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=openai_messages,
                max_tokens=1000,
                temperature=0.7,
            )

            response_content = completion.choices[0].message.content

            return ChatResponse(
                message=response_content, role="assistant", timestamp=datetime.now(UTC)
            )

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error communicating with OpenAI: {str(e)}",
            )
