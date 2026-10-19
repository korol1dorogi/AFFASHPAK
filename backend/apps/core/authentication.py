from rest_framework.authentication import SessionAuthentication as DrfSessionAuthentication


class SessionAuthentication(DrfSessionAuthentication):
    def authenticate_header(self, request):
        """Keep a missing session at 401, matching the contract.

        DRF turns NotAuthenticated into 403 when no challenge header is set.
        Session login has no browser prompt; the value only preserves the status.
        """
        return "Session"
