from django.conf import settings


def client_ip(request) -> str | None:
    """
    The caller's IP address, trusting only as many X-Forwarded-For hops as there are
    proxies we run (settings.REST_FRAMEWORK["NUM_PROXIES"]), the same rule DRF uses.
    """
    remote_addr = request.META.get("REMOTE_ADDR")
    num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if num_proxies > 0 and forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-min(num_proxies, len(hops))]
    return remote_addr
