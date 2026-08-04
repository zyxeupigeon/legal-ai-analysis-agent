class ProviderNotConfigured(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class ProviderInvalidResponse(RuntimeError):
    pass
