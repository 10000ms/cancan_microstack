from enum import StrEnum


class RedisKey(StrEnum):
    AUTH_ACCESS_KEY = "auth_access_token"
    AUTH_ACCESS_LOCK_KEY = "access_token_lock"
    USER_LOGIN_TOKEN_KEY = "user_login_token"
    USER_ID_TO_LOGIN_TOKEN_KEY = "user_id_to_login_token"
    USER_SESSION_KEY = "user_session_key"

    SERVICE_REGISTRY_PREFIX = "service_registry:"
    SERVICE_REGISTRY_INSTANCE = "instance:{service_name}:{instance_id}"
    SERVICE_REGISTRY_SERVICE_INSTANCES = "instances:{service_name}"
    SERVICE_REGISTRY_ALL_SERVICES = "all_services"
    SERVICE_REGISTRY_SERVICE_NAMES = "service_names"

    WORKFLOW_UPDATE_PREFIX = "workflow_update:"
