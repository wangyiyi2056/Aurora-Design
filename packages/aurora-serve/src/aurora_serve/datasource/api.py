from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from aurora_serve.datasource.schema import (
    DatasourceCreate,
    DatasourceListResponse,
    DatasourceResponse,
    DBConfig,
    QueryRequest,
    QueryResponse,
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


@router.post("", response_model=DatasourceResponse)
async def create_datasource(
    req: DatasourceCreate,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceResponse:
    service.add_connection(req.config)
    return DatasourceResponse(name=req.config.name, db_type=req.config.db_type)


@router.get("", response_model=DatasourceListResponse)
async def list_datasources(
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceListResponse:
    items = []
    for name in service.list_connections():
        conn = service.get_connector(name)
        try:
            tables = conn.get_table_names()
            items.append(
                DatasourceResponse(
                    name=name, db_type=conn.db_type, connected=True, tables=tables
                )
            )
        except Exception as e:
            items.append(
                DatasourceResponse(
                    name=name, db_type=conn.db_type, connected=False, error=str(e)
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
    return {"name": config.name, "db_type": config.db_type, "config": config.model_dump()}


@router.put("/{name}", response_model=DatasourceResponse)
async def update_datasource(
    name: str,
    req: DatasourceCreate,
    service: DatasourceService = Depends(get_datasource_service),
) -> DatasourceResponse:
    if req.config.name != name:
        raise HTTPException(status_code=422, detail="Datasource name cannot be changed")
    service.add_connection(req.config)
    return DatasourceResponse(name=req.config.name, db_type=req.config.db_type)


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
