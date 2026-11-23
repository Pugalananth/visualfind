import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Role = Literal["USER", "ADMIN"]
DetectionMode = Literal["person", "object", "auto"]


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name is required")
        return v


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.strip().lower()


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str
    confirm_password: str


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    notify_on_complete: bool | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class UserAdminUpdateIn(BaseModel):
    is_active: bool | None = None
    role: Role | None = None


class AdminSettingsIn(BaseModel):
    registration_enabled: bool | None = None
    min_password_length: int | None = Field(default=None, ge=8, le=64)
    default_threshold: float | None = Field(default=None, ge=0.5, le=0.95)
    default_detection_mode: DetectionMode | None = None
    max_video_mb: int | None = Field(default=None, ge=1, le=10000)
    max_url_download_mb: int | None = Field(default=None, ge=1, le=10000)
    url_download_timeout_s: int | None = Field(default=None, ge=5, le=1800)
    max_sampled_frames: int | None = Field(default=None, ge=10, le=20000)
    retention_days: int | None = Field(default=None, ge=0, le=3650)


PROVIDERS = ["custom", "huggingface", "aws_sagemaker", "azure_ml", "gcp_vertex"]


class ModelConfigIn(BaseModel):
    provider: str
    model_name: str = Field(min_length=1, max_length=120)
    endpoint_url: str = Field(min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    version: str | None = Field(default=None, max_length=60)
    options: dict | None = None

    @field_validator("provider")
    @classmethod
    def provider_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in PROVIDERS:
            raise ValueError(f"provider must be one of {', '.join(PROVIDERS)}")
        return v


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
