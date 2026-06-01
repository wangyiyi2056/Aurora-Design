from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from aurora_serve.datasource.schema import (
    DatabaseSummaryResponse,
    DatasourceCreate,
    DatasourceListResponse,
    DatasourceResponse,
    DatasourceTypesResponse,
    DBConfig,
    QueryRequest,
    QueryResponse,
    SavedQueryCreate,
    SavedQueryListResponse,
    SavedQueryResponse,
    SavedQueryUpdate,
    SchemaResponse,
)
from aurora_serve.datasource.service import DatasourceService

router = APIRouter(prefix="/datasource", tags=["datasource"])


def get_datasource_service(request: Request) -> DatasourceService:
    svc = getattr(request.app.state, "datasource_service", None)
    if svc is None:
        svc = DatasourceService()
        request.app.state.datasource_service = svc
    return svc


# ── test-connection must be before /{name} to avoid route conflict ──

@router.post("/test-connection", response_model=DatasourceResponse)
async def test_connection_config(
    config: DBConfig,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceResponse:
    ok, error = service.test_connection(config)
    return DatasourceResponse(
        name=config.name,
        db_type=config.db_type,
        connected=ok,
        error=error,
    )


@router.get("/types", response_model=DatasourceTypesResponse)
async def get_datasource_types(
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceTypesResponse:
    return service.get_supported_types()


# ── Saved Queries (static paths before /{name}) ──────────────────

@router.get("/saved-queries/{datasource_name}", response_model=SavedQueryListResponse)
async def list_saved_queries(
    datasource_name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> SavedQueryListResponse:
    items = service.list_saved_queries(datasource_name)
    return SavedQueryListResponse(items=[SavedQueryResponse(**item) for item in items])


@router.post("/saved-queries", response_model=SavedQueryResponse)
async def save_query(
    req: SavedQueryCreate,
    service: DatasourceService = Depends(get_datasource_service),
) -> SavedQueryResponse:
    result = service.save_query(req.datasource_name, req.sql, req.description)
    return SavedQueryResponse(**result)


@router.put("/saved-queries/{query_id}", response_model=SavedQueryResponse)
async def update_saved_query(
    query_id: str,
    req: SavedQueryUpdate,
    service: DatasourceService = Depends(get_datasource_service),
) -> SavedQueryResponse:
    result = service.update_saved_query(query_id, req.sql, req.description)
    if result is None:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return SavedQueryResponse(**result)


@router.delete("/saved-queries/{query_id}")
async def delete_saved_query(
    query_id: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> dict:
    ok = service.delete_saved_query(query_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return {"success": True}


@router.post("", response_model=DatasourceResponse)
async def create_datasource(
    req: DatasourceCreate,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceResponse:
    service.add_connection(req.config)
    entity = service.get_entity(req.config.name)
    return DatasourceResponse(
        name=req.config.name,
        db_type=req.config.db_type,
        description=req.config.description or "",
        created_at=entity.created_at if entity else None,
        updated_at=entity.updated_at if entity else None,
    )


@router.get("", response_model=DatasourceListResponse)
async def list_datasources(
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceListResponse:
    all_items = service.list_all()
    items = []
    for info in all_items:
        name = info["name"]
        try:
            conn = service.get_connector(name)
            tables = conn.get_table_names()
            items.append(
                DatasourceResponse(
                    name=name,
                    db_type=info["db_type"],
                    description=info.get("description", ""),
                    connected=True,
                    tables=tables,
                    created_at=info.get("created_at"),
                    updated_at=info.get("updated_at"),
                )
            )
        except Exception as e:
            items.append(
                DatasourceResponse(
                    name=name,
                    db_type=info["db_type"],
                    description=info.get("description", ""),
                    connected=False,
                    error=str(e),
                    created_at=info.get("created_at"),
                    updated_at=info.get("updated_at"),
                )
            )
    return DatasourceListResponse(items=items)


@router.delete("/{name}")
async def delete_datasource(
    name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> dict:
    ok = service.remove_connection(name)
    return {"success": ok}


@router.get("/{name}")
async def get_datasource(
    name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> dict:
    try:
        config = service.get_config(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Datasource not found")
    entity = service.get_entity(name)
    return {
        "name": config.name,
        "db_type": config.db_type,
        "description": config.description or "",
        "config": config.model_dump(),
        "created_at": entity.created_at if entity else None,
        "updated_at": entity.updated_at if entity else None,
    }


@router.put("/{name}", response_model=DatasourceResponse)
async def update_datasource(
    name: str,
    req: DatasourceCreate,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceResponse:
    if req.config.name != name:
        raise HTTPException(status_code=422, detail="Datasource name cannot be changed")
    service.add_connection(req.config)
    entity = service.get_entity(name)
    return DatasourceResponse(
        name=req.config.name,
        db_type=req.config.db_type,
        description=req.config.description or "",
        created_at=entity.created_at if entity else None,
        updated_at=entity.updated_at if entity else None,
    )


@router.post("/{name}/test", response_model=DatasourceResponse)
async def test_datasource(
    name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceResponse:
    conn = service.get_connector(name)
    try:
        tables = conn.get_table_names()
        return DatasourceResponse(
            name=name, db_type=conn.db_type, connected=True, tables=tables
        )
    except Exception as e:
        return DatasourceResponse(
            name=name, db_type=conn.db_type, connected=False, error=str(e)
        )


@router.post("/{name}/refresh")
async def refresh_datasource(
    name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> dict:
    try:
        ok = service.refresh(name)
        return {"success": ok}
    except KeyError:
        raise HTTPException(status_code=404, detail="Datasource not found")


@router.get("/{name}/summary", response_model=DatabaseSummaryResponse)
async def get_database_summary(
    name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatabaseSummaryResponse:
    try:
        summary = service.get_database_summary(name)
        return DatabaseSummaryResponse(
            name=name,
            db_type=summary.get("db_type", ""),
            tables=summary.get("tables", {}),
            relationships=summary.get("relationships", []),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Datasource not found")


@router.get("/{name}/tables")
async def get_tables(
    name: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> dict:
    conn = service.get_connector(name)
    return {"tables": conn.get_table_names()}


@router.get("/{name}/schema/{table}", response_model=SchemaResponse)
async def get_table_schema(
    name: str,
    table: str,
    service: DatasourceService = Depends(get_datasource_service),
) -> SchemaResponse:
    conn = service.get_connector(name)
    return SchemaResponse(name=table, schema_ddl=conn.get_table_schema(table))


@router.post("/{name}/query", response_model=QueryResponse)
async def run_query(
    name: str,
    req: QueryRequest,
    service: DatasourceService = Depends(get_datasource_service),
) -> QueryResponse:
    conn = service.get_connector(name)
    success, result = conn.run(req.sql)
    if success:
        return QueryResponse(success=True, result=result)
    return QueryResponse(success=False, result=None, error=result)
