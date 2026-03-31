import http.server
import socketserver

PORT = 8765

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Servidor local funcionando OK')
    def log_message(self, format, *args):
        pass

print(f'Iniciando servidor en puerto {PORT}...')
with socketserver.TCPServer(('localhost', PORT), Handler) as httpd:
    print(f'OK - Servidor corriendo en http://localhost:{PORT}')
    print('Abri ese link en el navegador para verificar')
    print('Ctrl+C para detener')
    httpd.serve_forever()