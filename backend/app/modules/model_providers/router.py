from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.rbac import require_permissions
from app.db.session import get_db
from app.models.ai_model import ModelProvider
from app.modules.auth.dependencies import CurrentUser, get_current_user

router = APIRouter()

PROVIDER_DEFAULT_BASE_URL = {
    "openai_compatible": "https://api.openai.com/v1",
    "codex_compatible": "https://api.openai.com/v1",
    "anthropic_compatible": "https://api.anthropic.com/v1",
    "claude_code_compatible": "https://api.anthropic.com/v1",
}
VALID_PROVIDER_TYPES = set(PROVIDER_DEFAULT_BASE_URL)


class ModelProviderPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_type: str = Field(min_length=1, max_length=40)
    base_url: str = Field(min_length=1)
    api_key: str | None = None
    default_model: str | None = Field(default=None, max_length=160)
    is_default: bool = False
    status: str = "active"


class ModelProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_type: str | None = Field(default=None, min_length=1, max_length=40)
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str | None = None
    default_model: str | None = Field(default=None, max_length=160)
    is_default: bool | None = None
    status: str | None = None


def _user_uuid(current_user: CurrentUser) -> UUID:
    return UUID(current_user.id)


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _validate_provider(provider_type: str, status_value: str) -> None:
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的模型服务类型")
    if status_value not in {"active", "inactive"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="状态只能是 active 或 inactive")


def serialize_provider(provider: ModelProvider) -> dict:
    return {
        "id": str(provider.id),
        "name": provider.name,
        "provider_type": provider.provider_type,
        "base_url": provider.base_url,
        "has_api_key": bool(provider.api_key_encrypted),
        "default_model": provider.default_model,
        "is_default": provider.is_default,
        "status": provider.status,
        "created_at": provider.created_at.isoformat() if provider.created_at else None,
        "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
    }


def _get_owned_provider(provider_id: UUID, user_id: UUID, db: Session) -> ModelProvider:
    provider = db.get(ModelProvider, provider_id)
    if provider is None or provider.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型配置不存在")
    return provider


def _clear_default(user_id: UUID, db: Session, exclude_id: UUID | None = None) -> None:
    query = update(ModelProvider).where(ModelProvider.user_id == user_id)
    if exclude_id:
        query = query.where(ModelProvider.id != exclude_id)
    db.execute(query.values(is_default=False))


async def _fetch_models(provider: ModelProvider) -> list[str]:
    api_key = decrypt_secret(provider.api_key_encrypted)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先配置 API Key")

    base_url = _normalize_base_url(provider.base_url)
    if provider.provider_type in {"anthropic_compatible", "claude_code_compatible"}:
        candidate_urls = [f"{base_url}/models"]
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        candidate_urls = [f"{base_url}/models"]
        if not base_url.endswith("/v1"):
            candidate_urls.append(f"{base_url}/v1/models")
        headers = {"Authorization": f"Bearer {api_key}"}

    timeout = httpx.Timeout(20.0, connect=8.0)
    last_error = ""
    payload = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in candidate_urls:
            try:
                response = await client.get(url, headers=headers)
            except httpx.TimeoutException:
                last_error = "模型服务连接超时"
                continue
            except httpx.HTTPError as exc:
                last_error = f"模型服务连接失败：{exc.__class__.__name__}"
                continue

            if response.status_code >= 400:
                last_error = f"模型服务连接失败：HTTP {response.status_code}"
                continue
            try:
                payload = response.json()
                break
            except ValueError:
                content_type = response.headers.get("content-type", "")
                last_error = f"模型服务返回非 JSON 内容：{content_type or 'unknown content-type'}"

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=last_error or "模型服务连接失败",
        )
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    names = []
    for item in items:
        model_id = item.get("id") if isinstance(item, dict) else None
        if model_id:
            names.append(str(model_id))
    return sorted(set(names))


@router.get("/provider-types", dependencies=[Depends(require_permissions("model_provider:list"))])
def list_provider_types():
    return {
        "items": [
            {
                "value": "openai_compatible",
                "label": "OpenAI",
                "default_base_url": PROVIDER_DEFAULT_BASE_URL["openai_compatible"],
            },
            {
                "value": "anthropic_compatible",
                "label": "Anthropic",
                "default_base_url": PROVIDER_DEFAULT_BASE_URL["anthropic_compatible"],
            },
        ]
    }


@router.get("", dependencies=[Depends(require_permissions("model_provider:list"))])
def list_model_providers(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user_id = _user_uuid(current_user)
    providers = db.scalars(
        select(ModelProvider)
        .where(ModelProvider.user_id == user_id)
        .order_by(ModelProvider.is_default.desc(), ModelProvider.created_at.asc())
    ).all()
    return {"items": [serialize_provider(provider) for provider in providers], "total": len(providers)}


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions("model_provider:create"))])
def create_model_provider(
    payload: ModelProviderPayload,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user_id = _user_uuid(current_user)
    provider_type = payload.provider_type.strip()
    status_value = payload.status.strip()
    _validate_provider(provider_type, status_value)
    if payload.is_default:
        _clear_default(user_id, db)
    provider = ModelProvider(
        user_id=user_id,
        name=payload.name.strip(),
        provider_type=provider_type,
        base_url=_normalize_base_url(payload.base_url),
        api_key_encrypted=encrypt_secret(payload.api_key.strip() if payload.api_key else None),
        default_model=payload.default_model.strip() if payload.default_model else None,
        is_default=payload.is_default,
        status=status_value,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return serialize_provider(provider)


@router.patch("/{provider_id}", dependencies=[Depends(require_permissions("model_provider:update"))])
def update_model_provider(
    provider_id: UUID,
    payload: ModelProviderPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user_id = _user_uuid(current_user)
    provider = _get_owned_provider(provider_id, user_id, db)
    provider_type = payload.provider_type.strip() if payload.provider_type else provider.provider_type
    status_value = payload.status.strip() if payload.status else provider.status
    _validate_provider(provider_type, status_value)
    if payload.is_default:
        _clear_default(user_id, db, exclude_id=provider.id)
    if payload.name is not None:
        provider.name = payload.name.strip()
    provider.provider_type = provider_type
    if payload.base_url is not None:
        provider.base_url = _normalize_base_url(payload.base_url)
    if payload.api_key is not None and payload.api_key.strip():
        provider.api_key_encrypted = encrypt_secret(payload.api_key.strip())
    if payload.default_model is not None:
        provider.default_model = payload.default_model.strip() or None
    if payload.is_default is not None:
        provider.is_default = payload.is_default
    provider.status = status_value
    db.commit()
    db.refresh(provider)
    return serialize_provider(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permissions("model_provider:delete"))])
def delete_model_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    provider = _get_owned_provider(provider_id, _user_uuid(current_user), db)
    db.delete(provider)
    db.commit()


@router.post("/{provider_id}/default", dependencies=[Depends(require_permissions("model_provider:update"))])
def set_default_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    user_id = _user_uuid(current_user)
    provider = _get_owned_provider(provider_id, user_id, db)
    _clear_default(user_id, db, exclude_id=provider.id)
    provider.is_default = True
    db.commit()
    db.refresh(provider)
    return serialize_provider(provider)


@router.get("/{provider_id}/models", dependencies=[Depends(require_permissions("model_provider:list"))])
async def fetch_provider_models(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    provider = _get_owned_provider(provider_id, _user_uuid(current_user), db)
    return {"items": await _fetch_models(provider)}


@router.post("/{provider_id}/test", dependencies=[Depends(require_permissions("model_provider:list"))])
async def test_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    provider = _get_owned_provider(provider_id, _user_uuid(current_user), db)
    models = await _fetch_models(provider)
    return {"ok": True, "model_count": len(models), "models": models[:20]}
