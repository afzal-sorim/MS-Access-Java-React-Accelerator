import os
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")

async def get_google_user(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Exchange Google OAuth code for user information."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured"
        )

    async with httpx.AsyncClient() as client:
        # Get endpoints from discovery
        resp = await client.get(GOOGLE_DISCOVERY_URL)
        endpoints = resp.json()
        token_endpoint = endpoints["token_endpoint"]
        userinfo_endpoint = endpoints["userinfo_endpoint"]

        # Exchange code for token
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        token_resp = await client.post(token_endpoint, data=data)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange Google code: {token_resp.text}"
            )

        token_data = token_resp.json()
        access_token = token_data["access_token"]

        # Get user info
        headers = {"Authorization": f"Bearer {access_token}"}
        user_resp = await client.get(userinfo_endpoint, headers=headers)
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch Google user info"
            )

        return user_resp.json()

async def get_github_user(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Exchange GitHub OAuth code for user information."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured"
        )

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_url = "https://github.com/login/oauth/access_token"
        data = {
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        }
        if redirect_uri:
            data["redirect_uri"] = redirect_uri

        headers = {"Accept": "application/json"}
        token_resp = await client.post(token_url, data=data, headers=headers)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange GitHub code"
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub OAuth error: {token_data.get('error_description', 'No access token')}"
            )

        # Get user profile
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/json"
        }
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub user info"
            )

        user_data = user_resp.json()

        # GitHub might not return email if it's private, fetch it separately
        if not user_data.get("email"):
            email_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            if email_resp.status_code == 200:
                emails = email_resp.json()
                primary_email = next((e["email"] for e in emails if e["primary"]), emails[0]["email"] if emails else None)
                user_data["email"] = primary_email

        return user_data
