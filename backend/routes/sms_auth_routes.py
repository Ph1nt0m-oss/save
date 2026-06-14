"""iter120 — Routes /auth/sms/* extraites de server.py.

2 endpoints liés à l'auth par code SMS (Twilio) :
  - POST /auth/sms/send
  - POST /auth/sms/verify

Le helper `send_sms_via_twilio` est inclus dans ce fichier (privé du module).
Helpers injectés : db, log_auth_error, logger.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class SMSAuthRequest(BaseModel):
    phone_number: str
    code: Optional[str] = None


def build_sms_auth_router(db, *, log_auth_error, logger):
    router = APIRouter()

    async def send_sms_via_twilio(phone_number: str, message: str) -> bool:
        """Send SMS via Twilio if configured, otherwise return False."""
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')

        if not all([twilio_sid, twilio_token, twilio_phone]):
            logger.warning("Twilio not configured - SMS will be simulated")
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                    auth=(twilio_sid, twilio_token),
                    data={
                        "From": twilio_phone,
                        "To": phone_number,
                        "Body": message,
                    },
                )

                if response.status_code in [200, 201]:
                    logger.info(f"SMS sent successfully to {phone_number}")
                    return True
                logger.error(f"Twilio error: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Twilio exception: {e}")
            return False

    @router.post("/auth/sms/send")
    async def send_sms_code(request: SMSAuthRequest):
        """Send SMS verification code (for offline auth)."""
        try:
            # Generate 6-digit code
            code = str(uuid.uuid4().int)[:6]

            await db.sms_codes.insert_one({
                "phone_number": request.phone_number,
                "code": code,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            message = f"Votre code CodeForge AI: {code}. Valide 5 minutes."
            sms_sent = await send_sms_via_twilio(request.phone_number, message)

            logger.info(f"SMS Code for {request.phone_number}: {code} (Twilio: {sms_sent})")

            response_data = {
                "message": "Code SMS envoyé" if sms_sent else "Code généré (mode démo)",
                "sms_sent": sms_sent,
            }

            # Return code in response only if Twilio is not configured (for testing)
            if not sms_sent:
                response_data["code"] = code  # DEMO MODE - remove when Twilio is configured

            return response_data
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/auth/sms/verify")
    async def verify_sms_code(request: SMSAuthRequest, response: Response):
        """Verify SMS code and create session."""
        try:
            code_doc = await db.sms_codes.find_one(
                {"phone_number": request.phone_number, "code": request.code},
                {"_id": 0},
            )

            if not code_doc:
                await log_auth_error("sms_invalid_code", f"phone={request.phone_number}", request=None)
                return JSONResponse(status_code=401, content={"detail": "Code invalide"})

            expires_at = datetime.fromisoformat(code_doc["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at < datetime.now(timezone.utc):
                await log_auth_error("sms_code_expired", f"phone={request.phone_number}", request=None)
                return JSONResponse(status_code=401, content={"detail": "Code expiré"})

            # Create or get user
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            existing_user = await db.users.find_one({"phone_number": request.phone_number}, {"_id": 0})

            if existing_user:
                user_id = existing_user["user_id"]
            else:
                new_user = {
                    "user_id": user_id,
                    "phone_number": request.phone_number,
                    "name": f"User {request.phone_number[-4:]}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await db.users.insert_one(new_user)

            # Create session
            session_token = f"sms_session_{uuid.uuid4().hex}"
            session_expires_at = datetime.now(timezone.utc) + timedelta(days=7)

            session_doc = {
                "session_token": session_token,
                "user_id": user_id,
                "auth_type": "sms",
                "expires_at": session_expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.user_sessions.insert_one(session_doc)

            # Set cookie
            response.set_cookie(
                key="session_token",
                value=session_token,
                httponly=True,
                secure=True,
                samesite="none",
                max_age=7 * 24 * 60 * 60,
                path="/",
            )

            # Delete used code
            await db.sms_codes.delete_one({"phone_number": request.phone_number, "code": request.code})

            user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
            return user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying SMS: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
