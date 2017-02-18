import unittest

from lib import manager


class TestLib(unittest.TestCase):
    def test_manager(self):
        ms = manager.RedisMetastore()
        ms.del_cloud('test')
        ms.put_cloud('test', ['a', 'b', 'c', 'd'])

        ds = manager.CloudDatastore(ms)
        fs = manager.Filesystem(manager.Manager('test', ms, ds))

        with fs.open('/foobar.txt', 'w') as f:
            f.write(b'test')
        with fs.open('/foobar.txt', 'r') as f:
            self.assertEqual(b'test', f.read())

        fs.mkdir('/bar')
        self.assertEqual(['bar', 'foobar.txt'], fs.ls('/'))

        fs.mkdir('/bar/foo')
        self.assertEqual(['foo'], fs.ls('/bar'))


if __name__ == '__main__':
    unittest.main()
