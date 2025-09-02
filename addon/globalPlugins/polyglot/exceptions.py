# -*- coding: utf-8 -*-

"""
This module defines all custom exception types for the add-on.
"""

class EngineError(Exception):
    """
    Base class for all exceptions related to translation engine interactions.
    Catching this exception can handle all known engine-related issues.
    """
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return str(self.message)

class NetworkConnectionError(EngineError):
    """
    Raised for retryable network-level errors (e.g., timeouts, DNS failures, connection refused).
    This is raised by the network module after multiple retry attempts have failed.
    """
    pass

class ApiResponseError(EngineError):
    """
    Raised when a network request is successful, but the API returns a business logic error
    (e.g., invalid API key, insufficient quota, bad parameters).
    """
    pass

class ResponseParsingError(EngineError):
    """
    Raised when the API's response cannot be parsed correctly (e.g., invalid JSON).
    """
    pass

class AuthenticationError(ApiResponseError):
    """
    A specific error for authentication failures.
    """
    pass