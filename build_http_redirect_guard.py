import urllib.request


class RedirectDenied(RuntimeError):
    """Raised before urllib follows an HTTP redirect during pinned build downloads."""

    def __init__(self, code: int, location: str | None) -> None:
        self.code = code
        self.location = location or ''
        super().__init__(f'HTTP redirect denied before follow: status={code}')


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # HTTPRedirectHandler calls this before opening newurl. Raising here keeps
        # the build runner from making any request to the redirect destination.
        raise RedirectDenied(code, headers.get('Location'))


NO_REDIRECT_OPENER = urllib.request.build_opener(NoRedirectHandler())
