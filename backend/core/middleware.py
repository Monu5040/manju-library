from django.utils.cache import add_never_cache_headers


class NoStoreApiMiddleware:
    """
    API answers carry personal data (mobile numbers, addresses, a TOTP secret during setup):
    browsers and proxies must not keep them, for example on a shared front-desk computer.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/") and not response.has_header("Cache-Control"):
            add_never_cache_headers(response)
        return response
