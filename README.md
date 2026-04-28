# exceptions.py

class ConnectError(Exception):
    """Chyba při připojení k serveru nebo neplatný login"""

    http_errors = {
        400: {"error": "BAD_REQUEST", "message": "The request was invalid or cannot be processed"},
        401: {"error": "AUTHENTICATION_FAILED", "message": "Authentication failed, invalid username or password"},
        403: {"error": "FORBIDDEN", "message": "Forbidden, insufficient permissions"},
        404: {"error": "NOT_FOUND", "message": "Requested resource not found"},
        500: {"error": "INTERNAL_SERVER_ERROR", "message": "Server encountered an unexpected error"},
        503: {"error": "SERVICE_UNAVAILABLE", "message": "Service unavailable, try again later"}
    } 

    def __init__(self, code: str | int):

        try:
            code_int = int(code)
        except (ValueError, TypeError):
            code_int = 400

        if code_int not in self.http_errors:
            code_int = 400

        self.code = code_int
        self.error = self.http_errors.get(self.code, {}).get("error")
        self.message = self.http_errors.get(self.code, {}).get("message")

        super().__init__(self.message)

class InvalidTokenError(Exception):
    """Chybný nebo expirovaný token"""
    def __init__(self):
        self.code = 401
        self.error = "INVALID_TOKEN"
        self.message = "Invalid or expired authentication token."
        super().__init__(self.message)

class SessionNotFoundError(Exception):
    """Nebyla nalezena aktivní session pro uživatele a server"""
    def __init__(self):
        self.code = 404
        self.error = "SESSION_NOT_FOUND"
        self.message = "No active session for this user and server."
        super().__init__(self.message)

class GenerationTokenError(Exception):
    """Chybný nebo expirovaný token"""
    def __init__(self):
        self.code = 500
        self.error = "GENERATION_TOKEN_FAILED"
        self.message = "Invalid or expired authentication token."
        super().__init__(self.message)

class InvalidCredentialsError(Exception):
    """Chybný nebo expirovaný token"""
    def __init__(self):
        self.code = 401
        self.error = "INVALID_CREDENTIALS"
        self.message = "Invalid username or password"
        super().__init__(self.message)

class ServerExistsError(Exception):
    def __init__(self, msg: str):

        self.code = 409
        self.error = "SERVER_EXISTS"
  
        self.message = msg

        super().__init__(self.message)

class ServerNotExistsError(Exception):
    def __init__(self):

        self.code = 409
        self.error = "SERVER_NOT_EXISTS"
        self.message = f"Server not exists"
        
        super().__init__(self.message)

class VmStatusNotSupportedError(Exception):
    def __init__(self, status: str):
        self.code = 400
        self.error = "VM_STATUS_NOT_SUPPORTED"
        self.message = f"VM status '{status}' is not supported."

        super().__init__(self.message)

class ServerNotFoundError(Exception):
    """Server nebyl nalezen"""
    def __init__(self, server_id: int):
        self.error = "SERVER_NOT_FOUND"
        self.message = f"Server with ID {server_id} not found."
        super().__init__(self.message)