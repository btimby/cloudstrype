class BaseError(Exception):
    pass


class PathNotFoundError(BaseError):
    pass


class FileNotFoundError(PathNotFoundError):
    pass


class DirectoryNotFoundError(PathNotFoundError):
    pass


class DirectoryNotEmptyError(BaseError):
    pass
