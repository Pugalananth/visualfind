from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import client_ip, get_db, require_admin
from ..schemas import ModelConfigIn
from ..services import audit, model_config
from ..services.url_guard import UrlError

router = APIRouter(prefix="/api/model", tags=["model"], dependencies=[Depends(require_admin)])


@router.get("")
async def get_model(db=Depends(get_db)):
    return model_config.public(await model_config.get_config(db))


@router.put("")
async def save_model(body: ModelConfigIn, request: Request, admin=Depends(require_admin), db=Depends(get_db)):
    try:
        await model_config.save_config(db, body.model_dump())
    except UrlError as exc:
        raise HTTPException(422, str(exc))
    result = await model_config.test_connection(db)  # validate by actually testing
    await audit.record(db, "admin.model_config_saved", actor=admin,
                       metadata={"provider": body.provider, "model": body.model_name, "status": result["status"]},
                       ip=client_ip(request))
    return {"config": model_config.public(await model_config.get_config(db)), "test": result}


@router.post("/test")
async def test_model(request: Request, admin=Depends(require_admin), db=Depends(get_db)):
    result = await model_config.test_connection(db)
    await audit.record(db, "admin.model_connection_tested", actor=admin, metadata={"status": result["status"]},
                       ip=client_ip(request))
    return result
