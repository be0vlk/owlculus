"""
Business logic for Strixy external service integration.

Provides OSINT-focused AI assistance through OpenAI integration with specialized
system prompts for intelligence gathering operations.

Key features:
- OSINT-specialized AI assistant for digital investigations
- Multi-domain intelligence support (SOCMINT, GEOINT, financial investigations)
- Professional investigation methodology guidance
- Secure OpenAI integration with API key management
"""

from datetime import UTC, datetime
from typing import List

from app.schemas.strixy_schema import ChatMessage, ChatResponse
from app.services.system_config_service import SystemConfigService
from fastapi import HTTPException, status
from openai import OpenAI
from sqlmodel import Session


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
You are Strixy, an expert AI assistant specialized in OSINT investigations within the Owlculus case management platform.

## Core Responsibilities
- Assist with OSINT research methodologies and digital investigation techniques
- Analyze and correlate information from open sources
- Suggest investigation strategies and evidence evaluation approaches

## Domain Expertise
- Digital forensics and cyber investigations
- Social media intelligence (SOCMINT)
- Geospatial intelligence (GEOINT)
- Financial investigations and cryptocurrency tracing
- Dark web research and monitoring
- Data correlation and pattern analysis

## Communication Guidelines
- Be precise, professional, and methodical
- Think step-by-step through investigation approaches
- Provide actionable, specific guidance
- Always consider legal and ethical boundaries
- Explain appropriate use cases for suggested tools

## Response Structure
1. Assess the investigation context
2. Suggest specific methodologies or tools

Maintain professional objectivity.""",
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
