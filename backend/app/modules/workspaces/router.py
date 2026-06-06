"""需求工作空间 API。"""
import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.data_scope import check_demand_data_permission
from app.core.rbac import require_permissions
from app.core.workspace import (
    ensure_demand_workspace,
    list_workspace_files,
    read_workspace_file,
    stage_file_path,
    write_workspace_file,
)
from app.db.session import SessionLocal, get_db
from app.models.demand import Demand
from app.models.local_bridge import DemandLocalProject, LocalBridgeClient, LocalBridgeCommand
from app.models.user import User
from app.modules.auth.dependencies import get_current_orm_user
from app.core.time import utc_now
from app.models.code_context import CodeContextScanResult, CodeContextSnapshot


router = APIRouter()


class WorkspaceFileUpdate(BaseModel):
    content: str


class LocalBridgeClientPayload(BaseModel):
    client_name: str = Field(min_length=1, max_length=120)
    client_key: str = Field(min_length=6, max_length=120)
    metadata: str | None = None


class LocalProjectPayload(BaseModel):
    project_key: str = Field(min_length=1, max_length=80)
    project_name: str = Field(min_length=1, max_length=120)
    local_path: str = Field(min_length=1)
    project_type: str = Field(default="service", max_length=50)
    branch_name: str | None = Field(default=None, max_length=120)
    bridge_client_id: UUID | None = None
    order_num: int = 0


class LocalBridgeCommandPayload(BaseModel):
    workflow_id: UUID | None = None
    local_project_id: UUID | None = None
    command_type: str = Field(default="shell", max_length=50)
    command_text: str = Field(min_length=1)


class BridgeCommandLogPayload(BaseModel):
    client_key: str = Field(min_length=6, max_length=120)
    chunk: str = ""
    status: str = Field(default="running", max_length=20)


class BridgeCommandCompletePayload(BaseModel):
    client_key: str = Field(min_length=6, max_length=120)
    status: str = Field(default="success", max_length=20)
    output_summary: str | None = None
    exit_code: int | None = None


class CodeContextSnapshotPayload(BaseModel):
    client_key: str = Field(min_length=6, max_length=120)
    demand_id: UUID
    source_ref: str | None = None
    root_path: str | None = None
    project_count: int = 0
    snapshot_content: str = Field(min_length=1)
    projects: list[dict] = []


class CodeContextConfirmPayload(BaseModel):
    project_keys: list[str] = Field(default_factory=list)


def _get_demand(demand_id: UUID, current_user: User, db: Session) -> Demand:
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    if not check_demand_data_permission(demand, current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该需求")
    return demand


def _serialize_workspace(workspace) -> dict:
    return {
        "id": str(workspace.id),
        "demand_id": str(workspace.demand_id),
        "company_id": str(workspace.company_id),
        "root_path": workspace.root_path,
        "status": workspace.status,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
    }


def _serialize_bridge_client(item: LocalBridgeClient) -> dict:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "client_name": item.client_name,
        "client_key": item.client_key,
        "status": item.status,
        "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
        "metadata": item.metadata_,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_local_project(item: DemandLocalProject) -> dict:
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "bridge_client_id": str(item.bridge_client_id) if item.bridge_client_id else None,
        "bridge_client_name": item.bridge_client.client_name if item.bridge_client else None,
        "project_key": item.project_key,
        "project_name": item.project_name,
        "local_path": item.local_path,
        "project_type": item.project_type,
        "branch_name": item.branch_name,
        "status": item.status,
        "order_num": item.order_num,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_bridge_command(item: LocalBridgeCommand) -> dict:
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "workflow_id": str(item.workflow_id) if item.workflow_id else None,
        "local_project_id": str(item.local_project_id) if item.local_project_id else None,
        "local_project_key": item.local_project.project_key if item.local_project else None,
        "local_project_name": item.local_project.project_name if item.local_project else None,
        "local_project_path": item.local_project.local_path if item.local_project else None,
        "bridge_client_id": str(item.bridge_client_id) if item.bridge_client_id else None,
        "command_type": item.command_type,
        "command_text": item.command_text,
        "status": item.status,
        "logs": item.logs,
        "output_summary": item.output_summary,
        "exit_code": item.exit_code,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_code_context(item: CodeContextSnapshot) -> dict:
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "source_type": item.source_type,
        "source_ref": item.source_ref,
        "root_path": item.root_path,
        "project_count": item.project_count,
        "snapshot_content": item.snapshot_content,
        "is_current": item.is_current,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _normalize_scanned_projects(projects: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, project in enumerate(projects):
        project_key = str(project.get("project_key") or project.get("name") or f"project-{index + 1}").strip()[:80]
        project_name = str(project.get("project_name") or project_key).strip()[:120]
        local_path = str(project.get("local_path") or "").strip()
        if not project_key or not local_path:
            continue
        normalized.append({
            "project_key": project_key,
            "project_name": project_name,
            "local_path": local_path,
            "project_type": str(project.get("project_type") or "service")[:50],
            "branch_name": str(project.get("branch_name") or "")[:120] or None,
        })
    return normalized


def _build_selected_snapshot_content(scan: CodeContextScanResult, selected_projects: list[dict]) -> str:
    lines = [
        "# Code Context Snapshot",
        "",
        f"- Root Path: {scan.root_path or '-'}",
        f"- Selected Project Count: {len(selected_projects)}",
        f"- Scanned Project Count: {scan.project_count}",
        "",
        "## Selected Projects",
    ]
    for project in selected_projects:
        lines.extend([
            "",
            f"### {project['project_key']}",
            f"- Name: {project['project_name']}",
            f"- Type: {project['project_type']}",
            f"- Path: {project['local_path']}",
        ])
    lines.extend(["", "## Bridge Scan Summary", scan.snapshot_content[:12000]])
    return "\n".join(lines)


def _serialize_code_context_scan_result(item: CodeContextScanResult) -> dict:
    try:
        projects = json.loads(item.projects_json or "[]")
    except json.JSONDecodeError:
        projects = []
    return {
        "id": str(item.id),
        "demand_id": str(item.demand_id),
        "bridge_client_id": str(item.bridge_client_id) if item.bridge_client_id else None,
        "bridge_client_name": item.bridge_client.client_name if item.bridge_client else None,
        "source_ref": item.source_ref,
        "root_path": item.root_path,
        "project_count": item.project_count,
        "projects": projects,
        "status": item.status,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _get_bridge_client_by_key(db: Session, client_key: str) -> LocalBridgeClient:
    client = db.scalar(select(LocalBridgeClient).where(LocalBridgeClient.client_key == client_key.strip()))
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bridge 客户端不存在")
    return client


@router.get("/{demand_id}/workspace", dependencies=[Depends(require_permissions("workspace:view"))])
def get_workspace(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = _get_demand(demand_id, current_user, db)
    workspace = ensure_demand_workspace(db, demand, current_user)
    db.commit()
    return _serialize_workspace(workspace)


@router.get("/{demand_id}/workspace/files", dependencies=[Depends(require_permissions("workspace:view"))])
def list_files(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = _get_demand(demand_id, current_user, db)
    workspace = ensure_demand_workspace(db, demand, current_user)
    db.commit()
    return {"items": list_workspace_files(workspace)}


@router.get("/{demand_id}/workspace/file", dependencies=[Depends(require_permissions("workspace:view"))])
def get_file(
    demand_id: UUID,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = _get_demand(demand_id, current_user, db)
    workspace = ensure_demand_workspace(db, demand, current_user)
    db.commit()
    return {"path": path, "content": read_workspace_file(workspace, path)}


@router.put("/{demand_id}/workspace/file", dependencies=[Depends(require_permissions("workspace:file:update"))])
def update_file(
    demand_id: UUID,
    path: str,
    payload: WorkspaceFileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = _get_demand(demand_id, current_user, db)
    workspace = ensure_demand_workspace(db, demand, current_user)
    write_workspace_file(workspace, path, payload.content)
    db.commit()
    return {"path": path, "message": "文件已保存"}


@router.get("/{demand_id}/workspace/stage-file", dependencies=[Depends(require_permissions("workspace:view"))])
def get_stage_file(
    demand_id: UUID,
    stage: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    demand = _get_demand(demand_id, current_user, db)
    workspace = ensure_demand_workspace(db, demand, current_user)
    db.commit()
    path = stage_file_path(stage)
    return {"path": path, "content": read_workspace_file(workspace, path)}


@router.get("/local-bridge/clients", dependencies=[Depends(require_permissions("local_bridge:view"))])
def list_bridge_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    query = (
        select(LocalBridgeClient)
        .where(LocalBridgeClient.user_id == current_user.id)
        .order_by(LocalBridgeClient.created_at.asc())
    )
    return {"items": [_serialize_bridge_client(item) for item in db.scalars(query).all()]}


@router.post("/local-bridge/clients", dependencies=[Depends(require_permissions("local_bridge:manage"))])
def upsert_bridge_client(
    payload: LocalBridgeClientPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    client = db.scalar(select(LocalBridgeClient).where(LocalBridgeClient.client_key == payload.client_key.strip()))
    if client and client.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bridge 标识已被其他用户使用")
    if not client:
        client = LocalBridgeClient(
            user_id=current_user.id,
            client_name=payload.client_name.strip(),
            client_key=payload.client_key.strip(),
            status="online",
            last_seen_at=utc_now(),
            metadata_=payload.metadata,
        )
        db.add(client)
    else:
        client.client_name = payload.client_name.strip()
        client.status = "online"
        client.last_seen_at = utc_now()
        client.metadata_ = payload.metadata
    db.commit()
    db.refresh(client)
    return _serialize_bridge_client(client)


@router.post("/local-bridge/clients/{client_id}/heartbeat", dependencies=[Depends(require_permissions("local_bridge:manage"))])
def heartbeat_bridge_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    client = db.get(LocalBridgeClient, client_id)
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bridge 客户端不存在")
    client.status = "online"
    client.last_seen_at = utc_now()
    db.commit()
    db.refresh(client)
    return _serialize_bridge_client(client)


@router.get("/{demand_id}/local-projects", dependencies=[Depends(require_permissions("local_project:view"))])
def list_local_projects(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    items = db.scalars(
        select(DemandLocalProject)
        .where(DemandLocalProject.demand_id == demand_id)
        .where(DemandLocalProject.status == "active")
        .order_by(DemandLocalProject.order_num.asc(), DemandLocalProject.created_at.asc())
    ).all()
    return {"items": [_serialize_local_project(item) for item in items]}


@router.post("/{demand_id}/local-projects", dependencies=[Depends(require_permissions("local_project:manage"))])
def create_local_project(
    demand_id: UUID,
    payload: LocalProjectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    if payload.bridge_client_id:
        client = db.get(LocalBridgeClient, payload.bridge_client_id)
        if not client or client.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bridge 客户端不可用")
    project = DemandLocalProject(
        demand_id=demand_id,
        bridge_client_id=payload.bridge_client_id,
        project_key=payload.project_key.strip(),
        project_name=payload.project_name.strip(),
        local_path=payload.local_path.strip(),
        project_type=payload.project_type.strip() or "service",
        branch_name=payload.branch_name.strip() if payload.branch_name else None,
        order_num=payload.order_num,
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _serialize_local_project(project)


@router.patch("/{demand_id}/local-projects/{project_id}", dependencies=[Depends(require_permissions("local_project:manage"))])
def update_local_project(
    demand_id: UUID,
    project_id: UUID,
    payload: LocalProjectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    project = db.get(DemandLocalProject, project_id)
    if not project or project.demand_id != demand_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地项目不存在")
    project.bridge_client_id = payload.bridge_client_id
    project.project_key = payload.project_key.strip()
    project.project_name = payload.project_name.strip()
    project.local_path = payload.local_path.strip()
    project.project_type = payload.project_type.strip() or "service"
    project.branch_name = payload.branch_name.strip() if payload.branch_name else None
    project.order_num = payload.order_num
    db.commit()
    db.refresh(project)
    return _serialize_local_project(project)


@router.delete("/{demand_id}/local-projects/{project_id}", dependencies=[Depends(require_permissions("local_project:manage"))])
def delete_local_project(
    demand_id: UUID,
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    project = db.get(DemandLocalProject, project_id)
    if not project or project.demand_id != demand_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本地项目不存在")
    project.status = "deleted"
    db.commit()
    return {"message": "本地项目已删除"}


@router.get("/{demand_id}/local-bridge/commands", dependencies=[Depends(require_permissions("local_bridge:view"))])
def list_bridge_commands(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    items = db.scalars(
        select(LocalBridgeCommand)
        .where(LocalBridgeCommand.demand_id == demand_id)
        .order_by(LocalBridgeCommand.created_at.desc())
    ).all()
    return {"items": [_serialize_bridge_command(item) for item in items]}


@router.post("/{demand_id}/local-bridge/commands", dependencies=[Depends(require_permissions("local_bridge:command"))])
def create_bridge_command(
    demand_id: UUID,
    payload: LocalBridgeCommandPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    project = db.get(DemandLocalProject, payload.local_project_id) if payload.local_project_id else None
    if payload.local_project_id and (not project or project.demand_id != demand_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地项目不可用")
    command = LocalBridgeCommand(
        demand_id=demand_id,
        workflow_id=payload.workflow_id,
        local_project_id=project.id if project else None,
        bridge_client_id=project.bridge_client_id if project else None,
        command_type=payload.command_type.strip() or "shell",
        command_text=payload.command_text.strip(),
        status="pending",
        created_by=current_user.id,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return _serialize_bridge_command(command)


@router.post("/{demand_id}/code-context/scan", dependencies=[Depends(require_permissions("code_context:create"))])
def request_code_context_scan(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    client = db.scalar(
        select(LocalBridgeClient)
        .where(LocalBridgeClient.user_id == current_user.id)
        .order_by(LocalBridgeClient.last_seen_at.desc().nullslast(), LocalBridgeClient.created_at.desc())
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先登记并启动本地 Bridge")
    command = LocalBridgeCommand(
        demand_id=demand_id,
        bridge_client_id=client.id,
        command_type="scan_workspace",
        command_text="scan_workspace",
        status="pending",
        created_by=current_user.id,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return _serialize_bridge_command(command)


@router.get("/{demand_id}/code-context", dependencies=[Depends(require_permissions("code_context:view"))])
def list_code_context_snapshots(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    items = db.scalars(
        select(CodeContextSnapshot)
        .where(CodeContextSnapshot.demand_id == demand_id)
        .order_by(CodeContextSnapshot.is_current.desc(), CodeContextSnapshot.created_at.desc())
    ).all()
    return {"items": [_serialize_code_context(item) for item in items]}


@router.get("/{demand_id}/code-context/scan-results/pending", dependencies=[Depends(require_permissions("code_context:view"))])
def get_pending_code_context_scan_result(
    demand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    item = db.scalar(
        select(CodeContextScanResult)
        .where(CodeContextScanResult.demand_id == demand_id)
        .where(CodeContextScanResult.status == "pending")
        .order_by(CodeContextScanResult.created_at.desc())
    )
    return {"item": _serialize_code_context_scan_result(item) if item else None}


@router.post("/{demand_id}/code-context/scan-results/{scan_result_id}/confirm", dependencies=[Depends(require_permissions("code_context:create"))])
def confirm_code_context_scan_result(
    demand_id: UUID,
    scan_result_id: UUID,
    payload: CodeContextConfirmPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    scan = db.get(CodeContextScanResult, scan_result_id)
    if not scan or scan.demand_id != demand_id or scan.status != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="待确认扫描结果不存在")
    projects = json.loads(scan.projects_json or "[]")
    selected_keys = {key.strip() for key in payload.project_keys if key.strip()}
    selected_projects = [project for project in projects if project.get("project_key") in selected_keys]
    if not selected_projects:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个本次需求相关项目")

    existing = db.scalars(
        select(CodeContextSnapshot)
        .where(CodeContextSnapshot.demand_id == demand_id)
        .where(CodeContextSnapshot.is_current.is_(True))
    ).all()
    for item in existing:
        item.is_current = False

    snapshot = CodeContextSnapshot(
        demand_id=demand_id,
        source_type="bridge",
        source_ref=scan.source_ref,
        root_path=scan.root_path,
        project_count=len(selected_projects),
        snapshot_content=_build_selected_snapshot_content(scan, selected_projects),
        is_current=True,
        created_by=current_user.id,
    )
    db.add(snapshot)
    for index, project in enumerate(selected_projects):
        existing_project = db.scalar(
            select(DemandLocalProject)
            .where(DemandLocalProject.demand_id == demand_id)
            .where(DemandLocalProject.project_key == project["project_key"])
        )
        if existing_project:
            existing_project.bridge_client_id = scan.bridge_client_id
            existing_project.project_name = project["project_name"]
            existing_project.local_path = project["local_path"]
            existing_project.project_type = project["project_type"]
            existing_project.branch_name = project["branch_name"]
            existing_project.status = "active"
            existing_project.order_num = index + 1
        else:
            db.add(DemandLocalProject(
                demand_id=demand_id,
                bridge_client_id=scan.bridge_client_id,
                project_key=project["project_key"],
                project_name=project["project_name"],
                local_path=project["local_path"],
                project_type=project["project_type"],
                branch_name=project["branch_name"],
                status="active",
                order_num=index + 1,
                created_by=current_user.id,
            ))
    scan.status = "confirmed"
    db.commit()
    db.refresh(snapshot)
    return _serialize_code_context(snapshot)


@router.post("/{demand_id}/code-context/scan-results/{scan_result_id}/ignore", dependencies=[Depends(require_permissions("code_context:create"))])
def ignore_code_context_scan_result(
    demand_id: UUID,
    scan_result_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_orm_user),
):
    _get_demand(demand_id, current_user, db)
    scan = db.get(CodeContextScanResult, scan_result_id)
    if not scan or scan.demand_id != demand_id or scan.status != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="待确认扫描结果不存在")
    scan.status = "ignored"
    db.commit()
    return {"message": "扫描结果已忽略"}


@router.post("/local-bridge/code-context")
def upload_bridge_code_context(
    payload: CodeContextSnapshotPayload,
    db: Session = Depends(get_db),
):
    # Bridge 上传的是候选扫描结果，用户确认相关项目后才会生成当前代码上下文。
    client = _get_bridge_client_by_key(db, payload.client_key)
    demand = db.get(Demand, payload.demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="需求不存在")
    existing_results = db.scalars(
        select(CodeContextScanResult)
        .where(CodeContextScanResult.demand_id == payload.demand_id)
        .where(CodeContextScanResult.status == "pending")
    ).all()
    for item in existing_results:
        item.status = "ignored"
    projects = _normalize_scanned_projects(payload.projects)
    scan_result = CodeContextScanResult(
        demand_id=payload.demand_id,
        bridge_client_id=client.id,
        source_ref=payload.source_ref,
        root_path=payload.root_path,
        project_count=len(projects),
        snapshot_content=payload.snapshot_content,
        projects_json=json.dumps(projects, ensure_ascii=False),
        status="pending",
        created_by=client.user_id,
    )
    db.add(scan_result)
    client.status = "online"
    client.last_seen_at = utc_now()
    db.commit()
    db.refresh(scan_result)
    return _serialize_code_context_scan_result(scan_result)


@router.get("/local-bridge/commands/pending")
def list_pending_bridge_commands(
    client_key: str,
    db: Session = Depends(get_db),
):
    client = _get_bridge_client_by_key(db, client_key)
    client.status = "online"
    client.last_seen_at = utc_now()
    items = db.scalars(
        select(LocalBridgeCommand)
        .where(LocalBridgeCommand.bridge_client_id == client.id)
        .where(LocalBridgeCommand.status == "pending")
        .order_by(LocalBridgeCommand.created_at.asc())
    ).all()
    db.commit()
    return {"items": [_serialize_bridge_command(item) for item in items]}


@router.post("/local-bridge/commands/{command_id}/claim")
def claim_bridge_command(
    command_id: UUID,
    payload: BridgeCommandLogPayload,
    db: Session = Depends(get_db),
):
    client = _get_bridge_client_by_key(db, payload.client_key)
    command = db.get(LocalBridgeCommand, command_id)
    if not command or command.bridge_client_id != client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="命令不存在")
    if command.status not in {"pending", "running"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="命令状态不可领取")
    command.status = "running"
    command.logs = (command.logs or "") + (payload.chunk or "")
    client.status = "online"
    client.last_seen_at = utc_now()
    db.commit()
    db.refresh(command)
    return _serialize_bridge_command(command)


@router.post("/local-bridge/commands/{command_id}/logs")
def append_bridge_command_logs(
    command_id: UUID,
    payload: BridgeCommandLogPayload,
    db: Session = Depends(get_db),
):
    client = _get_bridge_client_by_key(db, payload.client_key)
    command = db.get(LocalBridgeCommand, command_id)
    if not command or command.bridge_client_id != client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="命令不存在")
    command.status = payload.status if payload.status in {"pending", "running", "success", "failed", "cancelled"} else "running"
    if payload.chunk:
        command.logs = (command.logs or "") + payload.chunk
    client.status = "online"
    client.last_seen_at = utc_now()
    db.commit()
    db.refresh(command)
    return _serialize_bridge_command(command)


@router.post("/local-bridge/commands/{command_id}/complete")
def complete_bridge_command(
    command_id: UUID,
    payload: BridgeCommandCompletePayload,
    db: Session = Depends(get_db),
):
    client = _get_bridge_client_by_key(db, payload.client_key)
    command = db.get(LocalBridgeCommand, command_id)
    if not command or command.bridge_client_id != client.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="命令不存在")
    command.status = payload.status if payload.status in {"success", "failed", "cancelled"} else "failed"
    command.output_summary = payload.output_summary
    command.exit_code = payload.exit_code
    client.status = "online"
    client.last_seen_at = utc_now()
    db.commit()
    db.refresh(command)
    return _serialize_bridge_command(command)


@router.websocket("/local-bridge/ws")
async def bridge_websocket(websocket: WebSocket):
    # MVP 阶段通过 WebSocket 轮询推送待执行命令，命令日志和结果仍由 REST 回传，便于本地 Bridge 保持轻量。
    await websocket.accept()
    client_key = websocket.query_params.get("client_key", "")
    if not client_key:
        await websocket.send_json({"type": "error", "detail": "缺少 client_key"})
        await websocket.close()
        return
    try:
        while True:
            with SessionLocal() as db:
                try:
                    client = _get_bridge_client_by_key(db, client_key)
                    client.status = "online"
                    client.last_seen_at = utc_now()
                    items = db.scalars(
                        select(LocalBridgeCommand)
                        .where(LocalBridgeCommand.bridge_client_id == client.id)
                        .where(LocalBridgeCommand.status == "pending")
                        .order_by(LocalBridgeCommand.created_at.asc())
                    ).all()
                    db.commit()
                    await websocket.send_text(json.dumps({
                        "type": "commands",
                        "items": [_serialize_bridge_command(item) for item in items],
                    }, ensure_ascii=False))
                except HTTPException as exc:
                    await websocket.send_json({"type": "error", "detail": exc.detail})
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        return
