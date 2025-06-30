
"""
HTTP сервер для поддержания активности бота на Replit
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging

logger = logging.getLogger(__name__)

class KeepAliveHandler(BaseHTTPRequestHandler):
    def __init__(self, health_checker, *args, **kwargs):
        self.health_checker = health_checker
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Мой психолог - Telegram Bot</title>
                <meta charset="utf-8">
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                    .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                    .status { color: #28a745; font-weight: bold; }
                    .info { margin: 10px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 Мой психолог - Telegram Bot</h1>
                    <p class="status">✅ Бот активен и работает</p>
                    <div class="info">
                        <p><strong>Статус:</strong> Онлайн</p>
                        <p><strong>Технология:</strong> YandexGPT 3 (YaLM 2.0)</p>
                        <p><strong>Платформа:</strong> Replit</p>
                    </div>
                    <p>Найдите бота в Telegram и начните общение командой /start</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
            
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            health_status = self.health_checker.get_health_status()
            self.wfile.write(json.dumps(health_status, ensure_ascii=False).encode('utf-8'))
            
        elif self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'pong')
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Переопределяем логирование для уменьшения шума"""
        return

def create_keep_alive_handler(health_checker):
    """Создать обработчик с health_checker"""
    def handler(*args, **kwargs):
        return KeepAliveHandler(health_checker, *args, **kwargs)
    return handler

def keep_alive(health_checker, port=5000):
    """Запустить HTTP сервер для поддержания активности"""
    try:
        handler = create_keep_alive_handler(health_checker)
        server = HTTPServer(('0.0.0.0', port), handler)
        logger.info(f"Keep-alive сервер запущен на порту {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Ошибка keep-alive сервера: {e}")

def start_keep_alive_thread(health_checker, port=5000):
    """Запустить keep-alive сервер в отдельном потоке"""
    thread = threading.Thread(target=keep_alive, args=(health_checker, port), daemon=True)
    thread.start()
    logger.info("Keep-alive поток запущен")
    return thread
