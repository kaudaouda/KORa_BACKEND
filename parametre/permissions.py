"""Backward-compatibility shim — all logic lives in shared.permissions."""
from shared.permissions import (  # noqa: F401
    is_supervisor_smi,
    is_super_admin,
    can_manage_users,
    user_can_create_objectives_amendements,
    user_has_permission,
    user_can_create_for_processus,
    user_can_read_for_processus,
    user_can_delete_for_processus,
    user_can_validate_for_processus,
    get_user_processus_list,
    user_has_access_to_processus,
    user_has_write_permission_anywhere,
    check_permission_or_403,
)
