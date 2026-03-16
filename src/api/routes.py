"""FastAPI routes for Operation HOPE AI.

This module aggregates all domain-specific routers into a single APIRouter
for backward compatibility.  Individual routers live in src/api/routers/.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routers.auth_router import router as auth_router
from src.api.routers.tickets_router import router as tickets_router
from src.api.routers.approvals_router import router as approvals_router
from src.api.routers.kb_router import router as kb_router
from src.api.routers.admin_router import router as admin_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(tickets_router)
router.include_router(approvals_router)
router.include_router(kb_router)
router.include_router(admin_router)
