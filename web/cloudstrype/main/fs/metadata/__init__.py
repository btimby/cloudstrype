import abc


class BaseMetastore(metaclass=abc.ABCMeta):
    """
    Interface for a metastore.

    Metastores contain metadata about our filesystem. We use an ABC since we
    may implement different backends. Tests use a dummy backend that implements
    this interface.
    """

    @abc.abstractmethod
    def get_file(self, name):
        "Get chunks for given file."
        return

    @abc.abstractmethod
    def del_file(self, name):
        "Delete file from parent and it's chunk list."
        return

    @abc.abstractmethod
    def put_file(self, name, chunks=[]):
        "Create a file in it's parent and append any given chunks."
        return

    @abc.abstractmethod
    def get_dir(self, name):
        "Get the contents of a directory."
        return

    @abc.abstractmethod
    def del_dir(self, name):
        "Delete a directory."
        return

    @abc.abstractmethod
    def put_dir(self, name):
        "Create a directory."
        return
