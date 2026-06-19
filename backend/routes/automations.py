from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from joblogic_sdk.jicro import JicroClient, JicroError
from joblogic_sdk.odata import ODataClient, ODataError

router = APIRouter(prefix="/automations", tags=["automations"])


class ExecJicroRequest(BaseModel):
    tenant_id: str
    service_name: str
    message_signature: str
    payload: dict


class ODataQueryRequest(BaseModel):
    tenant_id: str
    service_name: str
    entity_name: str
    query_string: str
    include_soft_deleted: bool = False


@router.post("/exec")
async def exec_jicro(request: ExecJicroRequest):
    """Generic endpoint to execute any Jicro message."""
    try:
        async with JicroClient() as client:
            result = await client.execute(
                tenant_id=request.tenant_id,
                service_name=request.service_name,
                message_signature=request.message_signature,
                payload=request.payload,
            )
            return result
    except JicroError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@router.post("/odata-query")
async def odata_query(request: ODataQueryRequest):
    """Execute an OData query against any supported microservice entity."""
    try:
        async with ODataClient() as client:
            result = await client.query(
                tenant_id=request.tenant_id,
                service_name=request.service_name,
                entity_name=request.entity_name,
                query_string=request.query_string,
                include_soft_deleted=request.include_soft_deleted,
            )
            return result
    except ODataError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@router.post("/odata-count")
async def odata_count(request: ODataQueryRequest):
    """Count records matching an OData query against any supported microservice entity."""
    try:
        async with ODataClient() as client:
            count = await client.count(
                tenant_id=request.tenant_id,
                service_name=request.service_name,
                entity_name=request.entity_name,
                query_string=request.query_string,
                include_soft_deleted=request.include_soft_deleted,
            )
            return {"count": count}
    except ODataError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
