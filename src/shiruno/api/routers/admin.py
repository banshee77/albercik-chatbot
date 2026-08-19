"""GET /api/v1/admin/me — minimal authenticated admin identity endpoint
(feature 009-admin-platform-foundation, FR-019, FR-020).

Establishes the `/api/v1/admin/...` namespace future admin features build
under (research.md §4), without moving the existing `/api/v1/auth/login`
or `/api/v1/documents` routes. Depends on both `get_current_administrator`
and `get_current_tenant` — the caller's own tenant, always server-derived,
never influenced by any client-supplied value (FR-012, FR-013).
"""

from fastapi import APIRouter, Depends

from shiruno.api.deps import get_current_administrator, get_current_tenant
from shiruno.api.schemas import AdministratorOut, AdminMeResponse, TenantOut
from shiruno.persistence.models import Administrator, Tenant

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _to_response(administrator: Administrator, tenant: Tenant) -> AdminMeResponse:
    return AdminMeResponse(
        administrator=AdministratorOut(id=administrator.id, username=administrator.username),
        tenant=TenantOut(id=tenant.id, name=tenant.name, slug=tenant.slug),
    )


@router.get("/me", response_model=AdminMeResponse)
def get_me(
    current_admin: Administrator = Depends(get_current_administrator),
    current_tenant: Tenant = Depends(get_current_tenant),
) -> AdminMeResponse:
    return _to_response(current_admin, current_tenant)
