
"""
Модуль для проверки здоровья приложения
"""
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self):
        self.start_time = time.time()
        self.last_check = time.time()
        self.checks_count = 0
        
    def get_health_status(self) -> Dict[str, Any]:
        """Получить статус здоровья приложения"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        return {
            "status": "healthy",
            "uptime_seconds": round(uptime, 2),
            "uptime_human": self._format_uptime(uptime),
            "last_check": self._format_time(self.last_check),
            "checks_performed": self.checks_count,
            "timestamp": self._format_time(current_time)
        }
    
    def perform_check(self) -> bool:
        """Выполнить проверку здоровья"""
        try:
            self.last_check = time.time()
            self.checks_count += 1
            logger.info(f"Health check #{self.checks_count} passed")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def _format_uptime(self, seconds: float) -> str:
        """Форматировать время работы в читаемый вид"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"
    
    def _format_time(self, timestamp: float) -> str:
        """Форматировать временную метку"""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
