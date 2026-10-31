import os
import uuid
import datetime
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import duckdb
from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from app.sql_guard import (
    sanitize_and_validate_sql,
    create_secured_duckdb_connection,
    SQLGuardError,
)

METABRIDGE5_API_KEY = os.getenv("METABRIDGE5_API_KEY")
PARQUET_DATA_DIR = os.getenv("METABRIDGE5_PARQUET_DIR", "/data/parquet")

db_connection: duckdb.DuckDBPyConnection = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection
    db_connection = create_secured_duckdb_connection(data_dir=PARQUET_DATA_DIR)
    yield
    if db_connection:
        db_connection.close()

app = FastAPI(
    title="MetaBridge5 DuckDB Analytics",
    version="0.1.0",
    description="Vectorized Parquet partition pruning and columnar query engine",
    lifespan=lifespan,
)

def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    authorization: str = Header(None, alias="Authorization"),
):
    if not METABRIDGE5_API_KEY:
        return
    token = x_api_key
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
    if token != METABRIDGE5_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

class QueryRequest(BaseModel):
    sql_query: str

def serialize_value(val: Any) -> Any:
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    return val

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "duckdb-analytics"}

@app.post(
    "/api/v1/analytics/query",
    dependencies=[Depends(verify_api_key)],
    response_model=List[Dict[str, Any]],
)
async def execute_query_json(req: QueryRequest):
    try:
        sanitized_sql = sanitize_and_validate_sql(req.sql_query)
    except SQLGuardError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        res = db_connection.execute(sanitized_sql)
        cols = [c[0] for c in res.description]
        raw_rows = res.fetchall()
        rows = [
            {col: serialize_value(val) for col, val in zip(cols, row)}
            for row in raw_rows
        ]
        return rows
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post(
    "/api/v1/analytics/query.parquet",
    dependencies=[Depends(verify_api_key)],
)
async def execute_query_parquet(req: QueryRequest):
    try:
        sanitized_sql = sanitize_and_validate_sql(req.sql_query)
    except SQLGuardError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    temp_filename = f"/tmp/analytics/{uuid.uuid4().hex}.parquet"
    copy_sql = f"COPY ({sanitized_sql}) TO '{temp_filename}' (FORMAT PARQUET, COMPRESSION 'ZSTD');"

    try:
        db_connection.execute(copy_sql)
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    def cleanup_file():
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except OSError:
                pass

    return FileResponse(
        path=temp_filename,
        media_type="application/vnd.apache.parquet",
        filename="query_result.parquet",
        background=BackgroundTask(cleanup_file),
    )
