FS
--

Contains an FS-like interface to striped data. Written in Python as an async
HTTP server and client. The server-side exports a REST API that allows reading
and writing file data. The client-side reads and writes chunks of files striped
across storage providers.
