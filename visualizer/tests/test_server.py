import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer
from observer import allowed, handler_for


class Fake:
    def snapshot(self):
        return {'sessions':[], 'nodes':[], 'errors':[]}


class ServerTests(unittest.TestCase):
    def test_origin_and_host(self):
        self.assertTrue(allowed('127.0.0.1:8765', None, 8765))
        self.assertFalse(allowed('evil.example:8765', None, 8765))
        self.assertFalse(allowed('127.0.0.1:8765', 'http://evil.example', 8765))
        self.assertFalse(allowed('127.0.0.1:8765', 'null', 8765))

    def test_http(self):
        server = ThreadingHTTPServer(('127.0.0.1',0), handler_for(Fake()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            c = http.client.HTTPConnection('127.0.0.1',server.server_port)
            c.request('GET','/api/snapshot')
            r = c.getresponse()
            self.assertEqual(r.status,200)
            self.assertIn(b'"nodes": []',r.read())
            c.request('GET','/api/snapshot',headers={'Origin':'http://evil.example'})
            r = c.getresponse()
            self.assertEqual(r.status,403)
            r.read()
            c.request('GET','/../collector.py')
            r = c.getresponse()
            self.assertEqual(r.status,404)
            r.read()
            for path, mime in [('/office.js','text/javascript'),('/office.css','text/css'),('/classic','text/html')]:
                c.request('GET',path)
                r=c.getresponse()
                self.assertEqual(r.status,200)
                self.assertTrue(r.getheader('Content-Type').startswith(mime))
                self.assertTrue(r.read())
            c.close()
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    unittest.main()
