class BaseError(Exception):
    pass


class PathError(BaseError):
    def __init__(self, msg, path):
        self.path = path
        super().__init__(msg % path)


class PathNotFoundError(PathError):
    def __init__(self, path):
        super().__init__('path "%s" does not exist', path)


class FileNotFoundError(PathNotFoundError):
    def __init__(self, path):
        super().__init__('file "%s" does not exist', path)


class DirectoryNotFoundError(PathNotFoundError):
    def __init__(self, path):
        super().__init__('directory "%s" does not exist', path)


class DirectoryConflictError(PathError):
    def __init__(self, path):
        super().__init__('path "%s" exists as directory', path)


class FileConflictError(PathError):
    def __init__(self, path):
        super().__init__('path "%s" exists as file', path)


class DirectoryNotEmptyError(PathError):
    def __init__(self, path):
        super().__init__('directory "%s" not empty', path)
