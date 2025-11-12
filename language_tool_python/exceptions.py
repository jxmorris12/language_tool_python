class LanguageToolError(Exception):
    """
    Exception raised for errors in the LanguageTool library.
    This is a generic exception that can be used to indicate various types of
    errors encountered while using the LanguageTool library.
    """

    pass


class ServerError(LanguageToolError):
    """
    Exception raised for errors that occur when interacting with the LanguageTool server.
    This exception is a subclass of ``LanguageToolError`` and is used to indicate
    issues such as server startup failures.
    """

    pass


class JavaError(LanguageToolError):
    """
    Exception raised for errors related to the Java backend of LanguageTool.
    This exception is a subclass of ``LanguageToolError`` and is used to indicate
    issues that occur when interacting with Java, such as Java not being found.
    """

    pass


class PathError(LanguageToolError):
    """
    Exception raised for errors in the file path used in LanguageTool.
    This error is raised when there is an issue with the file path provided
    to LanguageTool, such as the LanguageTool JAR file not being found,
    or a download path not being a valid available file path.
    """

    pass


class RateLimitError(LanguageToolError):
    """
    Exception raised for errors related to rate limiting in the LanguageTool server.
    This exception is a subclass of ``LanguageToolError`` and is used to indicate
    issues such as exceeding the allowed number of requests to the public API without a key.
    """

    pass
