"""Skill 元数据 API。"""
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.db.session import get_db
from app.models.skill import Skill, WorkflowStageSkillBinding

router = APIRouter()
GITHUB_API_BASE = "https://api.github.com/repos"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"


class SkillRepositorySourcePayload(BaseModel):
    git_url: str = Field(min_length=1)
    git_ref: str = Field(default="main", min_length=1, max_length=120)
    root_path: str = Field(default="skills", max_length=200)
    entry_file: str = Field(default="SKILL.md", min_length=1, max_length=120)


def serialize_skill(skill: Skill) -> dict:
    return {
        "id": str(skill.id),
        "key": skill.key,
        "name": skill.name,
        "role": skill.role,
        "stage": skill.stage,
        "source": skill.source,
        "version": skill.version,
        "description": skill.description,
        "git_url": skill.git_url,
        "git_ref": skill.git_ref,
        "sub_path": skill.sub_path,
        "entry_file": skill.entry_file,
        "checksum": skill.checksum,
        "status": skill.status,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


def serialize_binding(binding: WorkflowStageSkillBinding, skill: Skill | None = None) -> dict:
    return {
        "id": str(binding.id),
        "template_key": binding.template_key,
        "stage_key": binding.stage_key,
        "skill_key": binding.skill_key,
        "is_default": binding.is_default,
        "order_num": binding.order_num,
        "status": binding.status,
        "skill": serialize_skill(skill) if skill else None,
    }


def _repository_root_from_skill(skill: Skill | None) -> str:
    if not skill or not skill.sub_path:
        return "skills"
    parts = skill.sub_path.strip("/").split("/")
    return parts[0] if parts else "skills"


def _skill_sub_path(root_path: str, skill_key: str) -> str:
    root = root_path.strip().strip("/")
    return _join_remote_path(root, skill_key) if root else skill_key


def _git_repo(git_url: str | None) -> dict | None:
    if not git_url:
        return None
    parsed = urlparse(git_url)
    path = parsed.path.strip("/")
    host = parsed.netloc.lower()
    if not host or not path:
        return None
    parts = path.removesuffix(".git").split("/")
    if len(parts) < 2:
        return None
    if host in {"github.com", "www.github.com"}:
        return {"provider": "github", "host": "github.com", "owner": parts[0], "repo": parts[1], "project": "/".join(parts[:2])}
    if host in {"gitee.com", "www.gitee.com"}:
        return {"provider": "gitee", "host": "gitee.com", "owner": parts[0], "repo": parts[1], "project": "/".join(parts[:2])}
    if host in {"gitlab.com", "www.gitlab.com"} or "gitlab" in host:
        return {"provider": "gitlab", "host": host, "project": "/".join(parts)}
    return None


def _skill_relative_root(skill: Skill) -> str:
    return (skill.sub_path or "").strip("/")


def _join_remote_path(*parts: str | None) -> str:
    return "/".join(part.strip("/") for part in parts if part and part.strip("/"))


async def _github_request_json(url: str) -> object | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenDevFlow",
    }
    timeout = httpx.Timeout(20.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def _github_request_text(url: str) -> str:
    timeout = httpx.Timeout(20.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "OpenDevFlow"})
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        return response.text


async def _list_remote_files(skill: Skill) -> list[dict]:
    repo = _git_repo(skill.git_url)
    if not repo:
        return []
    ref = quote(skill.git_ref or "main", safe="")
    root = _skill_relative_root(skill)
    files: list[dict] = []

    async def walk_github(path: str) -> None:
        encoded_path = quote(path, safe="/")
        url = f"{GITHUB_API_BASE}/{repo['owner']}/{repo['repo']}/contents/{encoded_path}?ref={ref}"
        payload = await _github_request_json(url)
        if not payload:
            return
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            item_path = item.get("path") or ""
            if item_type == "dir":
                await walk_github(item_path)
            elif item_type == "file":
                relative_path = item_path.removeprefix(f"{root}/") if root else item_path
                files.append({
                    "path": relative_path,
                    "name": relative_path.rsplit("/", 1)[-1],
                    "size": item.get("size") or 0,
                })

    async def walk_gitee(path: str) -> None:
        encoded_path = quote(path, safe="/")
        url = f"https://gitee.com/api/v5/repos/{repo['owner']}/{repo['repo']}/contents/{encoded_path}?ref={ref}"
        payload = await _github_request_json(url)
        if not payload:
            return
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            item_path = item.get("path") or item.get("name") or ""
            if item_type == "dir":
                await walk_gitee(item_path)
            elif item_type == "file":
                relative_path = item_path.removeprefix(f"{root}/") if root else item_path
                files.append({
                    "path": relative_path,
                    "name": relative_path.rsplit("/", 1)[-1],
                    "size": item.get("size") or 0,
                })

    async def list_gitlab() -> None:
        page = 1
        while True:
            project = quote(repo["project"], safe="")
            encoded_root = quote(root, safe="/")
            url = (
                f"https://{repo['host']}/api/v4/projects/{project}/repository/tree"
                f"?ref={ref}&path={encoded_root}&recursive=true&per_page=100&page={page}"
            )
            payload = await _github_request_json(url)
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                if not isinstance(item, dict) or item.get("type") != "blob":
                    continue
                item_path = item.get("path") or ""
                relative_path = item_path.removeprefix(f"{root}/") if root else item_path
                files.append({
                    "path": relative_path,
                    "name": relative_path.rsplit("/", 1)[-1],
                    "size": item.get("size") or 0,
                })
            if len(payload) < 100:
                break
            page += 1

    if repo["provider"] == "github":
        await walk_github(root)
    elif repo["provider"] == "gitee":
        await walk_gitee(root)
    elif repo["provider"] == "gitlab":
        await list_gitlab()
    return sorted(files, key=lambda item: item["path"])


async def _read_remote_file(skill: Skill, relative_path: str) -> str:
    repo = _git_repo(skill.git_url)
    if not repo:
        return ""
    path_parts = relative_path.split("/")
    if not relative_path or relative_path.startswith("/") or ".." in path_parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件路径不合法")
    ref = quote(skill.git_ref or "main", safe="")
    file_path = quote(_join_remote_path(_skill_relative_root(skill), relative_path), safe="/")
    if repo["provider"] == "github":
        url = f"{GITHUB_RAW_BASE}/{repo['owner']}/{repo['repo']}/{ref}/{file_path}"
    elif repo["provider"] == "gitee":
        url = f"https://gitee.com/{repo['owner']}/{repo['repo']}/raw/{ref}/{file_path}"
    elif repo["provider"] == "gitlab":
        project = quote(repo["project"], safe="")
        encoded_file_path = quote(_join_remote_path(_skill_relative_root(skill), relative_path), safe="")
        url = f"https://{repo['host']}/api/v4/projects/{project}/repository/files/{encoded_file_path}/raw?ref={ref}"
    else:
        return ""
    return await _github_request_text(url)


@router.get("", dependencies=[Depends(require_permissions("system:skill:list"))])
def list_skills(
    stage: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = select(Skill).where(Skill.status == "active")
    if stage:
        query = query.where(Skill.stage.in_([stage, "all"]))
    query = query.order_by(Skill.stage.asc(), Skill.role.asc(), Skill.key.asc())
    skills = db.scalars(query).all()
    return {"items": [serialize_skill(skill) for skill in skills], "total": len(skills)}


@router.get("/stage-bindings", dependencies=[Depends(require_permissions("system:skill:list"))])
def list_stage_skill_bindings(
    template_key: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = select(WorkflowStageSkillBinding).where(WorkflowStageSkillBinding.status == "active")
    if template_key:
        query = query.where(WorkflowStageSkillBinding.template_key == template_key)
    if stage:
        query = query.where(WorkflowStageSkillBinding.stage_key == stage)
    query = query.order_by(WorkflowStageSkillBinding.template_key.asc(), WorkflowStageSkillBinding.stage_key.asc(), WorkflowStageSkillBinding.order_num.asc())
    bindings = db.scalars(query).all()
    skill_by_key = {
        skill.key: skill
        for skill in db.scalars(select(Skill).where(Skill.key.in_([binding.skill_key for binding in bindings]))).all()
    } if bindings else {}
    return {
        "items": [serialize_binding(binding, skill_by_key.get(binding.skill_key)) for binding in bindings],
        "total": len(bindings),
    }


@router.get("/repository-source", dependencies=[Depends(require_permissions("system:skill:list"))])
def get_skill_repository_source(
    db: Session = Depends(get_db),
):
    skill = db.scalar(
        select(Skill)
        .where(Skill.status == "active")
        .order_by(Skill.key.asc())
        .limit(1)
    )
    if not skill:
        return {
            "git_url": "",
            "git_ref": "main",
            "root_path": "skills",
            "entry_file": "SKILL.md",
            "skill_count": 0,
        }
    skill_count = db.scalar(select(func.count()).select_from(Skill).where(Skill.status == "active"))
    return {
        "git_url": skill.git_url or "",
        "git_ref": skill.git_ref or "main",
        "root_path": _repository_root_from_skill(skill),
        "entry_file": skill.entry_file or "SKILL.md",
        "skill_count": skill_count or 0,
    }


@router.patch("/repository-source", dependencies=[Depends(require_permissions("system:skill:list"))])
def update_skill_repository_source(
    payload: SkillRepositorySourcePayload,
    db: Session = Depends(get_db),
):
    git_url = payload.git_url.strip()
    if not _git_repo(git_url):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 GitHub、Gitee、GitLab 仓库地址")
    skills = db.scalars(select(Skill).where(Skill.status == "active")).all()
    root_path = payload.root_path.strip().strip("/")
    entry_file = payload.entry_file.strip().strip("/") or "SKILL.md"
    git_ref = payload.git_ref.strip()
    for skill in skills:
        skill.git_url = git_url
        skill.git_ref = git_ref
        skill.sub_path = _skill_sub_path(root_path, skill.key)
        skill.entry_file = entry_file
    db.commit()
    return {
        "git_url": git_url,
        "git_ref": git_ref,
        "root_path": root_path or "",
        "entry_file": entry_file,
        "skill_count": len(skills),
    }


@router.get("/{skill_key}", dependencies=[Depends(require_permissions("system:skill:list"))])
async def get_skill_detail(
    skill_key: str,
    file: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    skill = db.scalar(select(Skill).where(Skill.key == skill_key))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    if not _git_repo(skill.git_url):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill 必须配置 GitHub、Gitee 或 GitLab 仓库地址")
    entry_file = file or skill.entry_file or "SKILL.md"
    try:
        files = await _list_remote_files(skill)
        content = await _read_remote_file(skill, entry_file)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Git Skill 内容读取失败：{exc.__class__.__name__}") from exc
    return {
        **serialize_skill(skill),
        "entry_content": content,
        "entry_file": entry_file,
        "files": files,
        "content_available": bool(content),
        "content_source": "git",
    }
