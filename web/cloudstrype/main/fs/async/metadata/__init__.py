import abc


class BaseMetastore:
    __metaclass__ = abc.ABCMeta

    @abstractmethod
    def get_file(self, name):
        pass

    @abstractmethod
    def del_file(self, name):
        pass

    @abstractmethod
    def put_file(self, name, chunks=[]):
        pass

    @abstractmethod
    def get_dir(self, name):
        pass

    @abstractmethod
    def del_dir(self, name):
        pass

    @abstractmethod
    def put_dir(self, name):
        pass


