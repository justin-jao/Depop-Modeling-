import http.server
import socketserver
import os
import sys

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Prevent caching for development
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    # Ensure working directory is the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Handle port in use by trying next ports
    port = PORT
    while port < PORT + 10:
        try:
            with socketserver.TCPServer(("", port), Handler) as httpd:
                print(f"\n==============================================")
                print(f"  VOGUE ANALYTICS DEV SERVER RUNNING")
                print(f"  URL: http://localhost:{port}")
                print(f"  Directory: {script_dir}")
                print(f"  Press Ctrl+C to stop")
                print(f"==============================================\n")
                httpd.serve_forever()
        except OSError as e:
            if e.errno == 48: # Address already in use
                print(f"Port {port} is in use, trying {port + 1}...")
                port += 1
            else:
                raise e
        except KeyboardInterrupt:
            print("\nStopping dev server...")
            sys.exit(0)
