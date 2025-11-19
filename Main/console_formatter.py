"""
Console Formatter and Beautification Module
==============================================

Provides beautiful, structured console output with colors, formatting,
and progress indicators for better visibility of backend operations.
"""

import sys
from datetime import datetime
from typing import Optional


class Colors:
    """ANSI color codes"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'
    
    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'


class ConsoleFormatter:
    """Beautiful console output formatter"""
    
    # Configuration
    ENABLE_COLORS = sys.stdout.isatty()  # Only use colors if terminal supports it
    SECTION_WIDTH = 80
    TIMESTAMP_FORMAT = '%H:%M:%S'
    
    @staticmethod
    def _colored(text: str, color: str) -> str:
        """Apply color to text"""
        if not ConsoleFormatter.ENABLE_COLORS:
            return text
        return f"{color}{text}{Colors.RESET}"
    
    @staticmethod
    def timestamp() -> str:
        """Get current timestamp"""
        now = datetime.now().strftime(ConsoleFormatter.TIMESTAMP_FORMAT)
        return ConsoleFormatter._colored(f"[{now}]", Colors.GRAY)
    
    @staticmethod
    def section(title: str) -> str:
        """Format section header"""
        separator = '=' * (ConsoleFormatter.SECTION_WIDTH - len(title) - 4)
        header = f"\n{ConsoleFormatter._colored(f'╔ {title} {separator}', Colors.BOLD + Colors.CYAN)}\n"
        return header
    
    @staticmethod
    def subsection(title: str) -> str:
        """Format subsection header"""
        return f"\n{ConsoleFormatter._colored(f'├─ {title}', Colors.CYAN)}\n"
    
    @staticmethod
    def success(message: str,               prefix: str = "✅ SUCCESS           ") -> str:
        """Format success message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def error(message: str,                 prefix: str = "❌ ERROR             ") -> str:
        """Format error message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.RED)} {message}"
    
    @staticmethod
    def warning(message: str,               prefix: str = "⚠️  WARNING           ") -> str:
        """Format warning message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def info(message: str,                  prefix: str = "ℹ️  INFO              ") -> str:
        """Format info message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def processing(message: str,            prefix: str = "🔄 PROCESSING        ") -> str:
        """Format processing message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.MAGENTA)} {message}"
    
    @staticmethod
    def data(message: str,                  prefix: str = "📊 DATA              ") -> str:
        """Format data message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def file_op(message: str,               prefix: str = "📁 FILE OPERATION    ") -> str:
        """Format file operation message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def network(message: str,               prefix: str = "🌐 NETWORK           ") -> str:
        """Format network message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.CYAN)} {message}"
    
    @staticmethod
    def route(message: str, prefix: str = "🛣️ ROUTE             ") -> str:
        """Format route message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def metric(label: str, value: str, unit: str = "") -> str:
        """Format metric display"""
        value_colored = ConsoleFormatter._colored(f"{value}{unit}", Colors.BOLD + Colors.GREEN)
        return f"   {label}: {value_colored}"
    
    @staticmethod
    def progress_bar(current: int, total: int, width: int = 20) -> str:
        """Generate progress bar"""
        if total == 0:
            percentage = 0
            filled = 0
        else:
            percentage = int((current / total) * 100)
            filled = int((current / total) * width)
        
        bar = '█' * filled + '░' * (width - filled)
        bar_colored = ConsoleFormatter._colored(bar, Colors.GREEN)
        return f"{bar_colored} {percentage}%"
    
    @staticmethod
    def table_header(columns: list) -> str:
        """Format table header"""
        widths = [20] * len(columns)
        header = " | ".join(col.ljust(w) for col, w in zip(columns, widths))
        separator = "-" * (sum(widths) + len(columns) * 3 - 1)
        return f"{ConsoleFormatter._colored(header, Colors.BOLD)}\n{separator}"
    
    @staticmethod
    def table_row(values: list, colors_list: Optional[list] = None) -> str:
        """Format table row"""
        widths = [20] * len(values)
        if colors_list is None:
            colors_list = [Colors.RESET] * len(values)
        
        cells = []
        for val, col in zip(values, colors_list):
            cell = str(val).ljust(20)
            if col and ConsoleFormatter.ENABLE_COLORS:
                cell = f"{col}{cell}{Colors.RESET}"
            cells.append(cell)
        
        return " | ".join(cells)
    
    @staticmethod
    def indent(message: str, level: int = 1, char: str = "  ") -> str:
        """Indent message"""
        return char * level + message
    
    @staticmethod
    def divider(char: str = "─", width: Optional[int] = None) -> str:
        """Print divider line"""
        if width is None:
            width = ConsoleFormatter.SECTION_WIDTH
        return ConsoleFormatter._colored(char * width, Colors.DIM)
    
    @staticmethod
    def database(message: str,              prefix: str = "🗄️ DATABASE          ") -> str:
        """Format database message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def security(message: str,              prefix: str = "🔐 SECURITY          ") -> str:
        """Format security/auth message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.MAGENTA)} {message}"
    
    @staticmethod
    def performance(message: str,           prefix: str = "⚡ PERFORMANCE       ") -> str:
        """Format performance message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def config(message: str,                prefix: str = "⚙️  CONFIG            ") -> str:
        """Format configuration message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.CYAN)} {message}"
    
    @staticmethod
    def test(message: str,                  prefix: str = "🧪 TEST              ") -> str:
        """Format test message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def api(message: str,                   prefix: str = "🔗 API               ") -> str:
        """Format API message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def cache(message: str,                 prefix: str = "💾 CACHE             ") -> str:
        """Format cache message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.CYAN)} {message}"
    
    @staticmethod
    def memory(message: str,                prefix: str = "🧠 MEMORY            ") -> str:
        """Format memory message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.MAGENTA)} {message}"
    
    @staticmethod
    def disk(message: str,                  prefix: str = "💿 DISK              ") -> str:
        """Format disk I/O message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def time(message: str,                  prefix: str = "⏱️  TIME              ") -> str:
        """Format timing message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def validation(message: str,            prefix: str = "✅ VALIDATION        ") -> str:
        """Format validation message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def error_validation(message: str,      prefix: str = "❌ ERROR VALIDATION  ") -> str:
        """Format validation error message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.RED)} {message}"
    
    @staticmethod
    def warning_validation(message: str,    prefix: str = "⚠️  WARNING VALIDATION") -> str:
        """Format validation warning message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def location(message: str,              prefix: str = "📍 LOCATION          ") -> str:
        """Format location/GPS message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def traffic(message: str,               prefix: str = "🚦  TRAFFIC           ") -> str:
        """Format traffic message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.RED)} {message}"
    
    @staticmethod
    def incident(message: str,              prefix: str = "🚨 INCIDENT          ") -> str:
        """Format incident message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.RED)} {message}"
    
    @staticmethod
    def disruption(message: str,            prefix: str = "🔧 DISRUPTION        ") -> str:
        """Format disruption message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def algorithm(message: str,             prefix: str = "🧮 ALGORITHM         ") -> str:
        """Format algorithm message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.MAGENTA)} {message}"
    
    @staticmethod
    def graph(message: str,                 prefix: str = "📈 GRAPH             ") -> str:
        """Format graph/network message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.CYAN)} {message}"
    
    @staticmethod
    def osm(message: str,                   prefix: str = "🗺️  OSM               ") -> str:
        """Format OSM/OpenStreetMap message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def download(message: str,              prefix: str = "⬇️ DOWNLOAD          ") -> str:
        """Format download message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def upload(message: str,                prefix: str = "⬆️ UPLOAD            ") -> str:
        """Format upload message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def server(message: str,                prefix: str = "🖥️  SERVER            ") -> str:
        """Format server message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.GREEN)} {message}"
    
    @staticmethod
    def client(message: str,                prefix: str = "💻 CLIENT            ") -> str:
        """Format client message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"
    
    @staticmethod
    def thread(message: str,                prefix: str = "🧵 THREAD            ") -> str:
        """Format thread message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.MAGENTA)} {message}"
    
    @staticmethod
    def process(message: str,               prefix: str = "⚙️ PROCESS           ") -> str:
        """Format process message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.CYAN)} {message}"
    
    @staticmethod
    def network(message: str,               prefix: str = "🌐 NETWORK           ") -> str:
        """Format network message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.CYAN)} {message}"
    
    @staticmethod
    def file_op(message: str,               prefix: str = "📁 FILE              ") -> str:
        """Format file operation message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def wait(message: str,                  prefix: str = "⏳ WAIT              ") -> str:
        """Format wait message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.YELLOW)} {message}"
    
    @staticmethod
    def search(message: str,                prefix: str = "🔍  SEARCH            ") -> str:
        """Format search message"""
        return f"{ConsoleFormatter.timestamp()} {ConsoleFormatter._colored(prefix, Colors.BLUE)} {message}"


class LogLevel:
    """Log level constants"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """Structured logging with beautiful formatting"""
    
    def __init__(self, name: str):
        self.name = name
    
    def _log(self, level: str, message: str, formatter_func) -> str:
        """Internal logging method"""
        formatted = formatter_func(message)
        print(formatted)
        return formatted
    
    def debug(self, message: str) -> str:
        """Log debug message"""
        return self._log(LogLevel.DEBUG, f"[{self.name}] {message}", ConsoleFormatter.info)
    
    def info(self, message: str) -> str:
        """Log info message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.info)
    
    def success(self, message: str) -> str:
        """Log success message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.success)
    
    def warning(self, message: str) -> str:
        """Log warning message"""
        return self._log(LogLevel.WARNING, f"[{self.name}] {message}", ConsoleFormatter.warning)
    
    def error(self, message: str) -> str:
        """Log error message"""
        return self._log(LogLevel.ERROR, f"[{self.name}] {message}", ConsoleFormatter.error)
    
    def critical(self, message: str) -> str:
        """Log critical message"""
        return self._log(LogLevel.CRITICAL, f"[{self.name}] {message}", ConsoleFormatter.error)
    
    def processing(self, message: str) -> str:
        """Log processing message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.processing)
    
    def data(self, message: str) -> str:
        """Log data message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.data)
    
    def network(self, message: str) -> str:
        """Log network message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.network)
    
    def database(self, message: str) -> str:
        """Log database message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.database)
    
    def security(self, message: str) -> str:
        """Log security message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.security)
    
    def performance(self, message: str) -> str:
        """Log performance message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.performance)
    
    def config(self, message: str) -> str:
        """Log configuration message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.config)
    
    def test(self, message: str) -> str:
        """Log test message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.test)
    
    def api(self, message: str) -> str:
        """Log API message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.api)
    
    def cache(self, message: str) -> str:
        """Log cache message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.cache)
    
    def memory(self, message: str) -> str:
        """Log memory message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.memory)
    
    def disk(self, message: str) -> str:
        """Log disk I/O message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.disk)
    
    def time(self, message: str) -> str:
        """Log timing message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.time)
    
    def validation(self, message: str) -> str:
        """Log validation message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.validation)
    
    def location(self, message: str) -> str:
        """Log location message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.location)
    
    def traffic(self, message: str) -> str:
        """Log traffic message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.traffic)
    
    def incident(self, message: str) -> str:
        """Log incident message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.incident)
    
    def disruption(self, message: str) -> str:
        """Log disruption message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.disruption)
    
    def algorithm(self, message: str) -> str:
        """Log algorithm message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.algorithm)
    
    def graph(self, message: str) -> str:
        """Log graph message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.graph)
    
    def osm(self, message: str) -> str:
        """Log OSM message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.osm)
    
    def download(self, message: str) -> str:
        """Log download message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.download)
    
    def upload(self, message: str) -> str:
        """Log upload message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.upload)
    
    def server(self, message: str) -> str:
        """Log server message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.server)
    
    def client(self, message: str) -> str:
        """Log client message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.client)
    
    def thread(self, message: str) -> str:
        """Log thread message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.thread)
    
    def process(self, message: str) -> str:
        """Log process message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.process)

    def wait(self, message: str) -> str:
        """Log wait message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.wait)
    
    def file_op(self, message: str) -> str:
        """Log file operation message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.file_op)
    
    def search(self, message: str) -> str:
        """Log search message"""
        return self._log(LogLevel.INFO, f"[{self.name}] {message}", ConsoleFormatter.search)

def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)
