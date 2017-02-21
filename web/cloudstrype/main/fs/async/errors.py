class BaseError(Exception):
    pass


class FileNotFoundError(BaseError):
    pass


class DirectoryNotFoundError(BaseError):
    pass


class DirectoryNotEmptyError(BaseError):
    pass
