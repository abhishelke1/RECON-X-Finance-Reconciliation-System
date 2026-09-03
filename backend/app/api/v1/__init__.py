"""API V1 Router."""
from fastapi import APIRouter

from app.api.v1.system_routes import router as system_router

router = APIRouter()
router.include_router(system_router, tags=["system"])
from app.api.v1.import_routes import router as import_router
from app.api.v1.reconciliation_routes import router as reconciliation_router
from app.api.v1.exception_routes import router as exception_router
from app.api.v1.audit_routes import router as audit_router
from app.api.v1.evaluation_routes import router as evaluation_router

router.include_router(import_router, tags=["import"])
router.include_router(reconciliation_router, tags=["reconciliation"])
router.include_router(exception_router, tags=["exceptions"])
router.include_router(audit_router, tags=["audit"])
router.include_router(evaluation_router, tags=["evaluation"])
