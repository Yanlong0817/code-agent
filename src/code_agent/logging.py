"""日志配置模块。"""

import logging
import sys
from pathlib import Path
from typing import Literal

# 日志级别类型
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s - %(message)s"


def setup_logging(
    level: LogLevel = "INFO",
    log_file: Path | None = None,
    format_string: str = DEFAULT_FORMAT,
    console_output: bool = False,
) -> logging.Logger:
    """配置并返回 code_agent 的根日志记录器。

    Args:
        level: 日志级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）
        log_file: 日志文件路径
        format_string: 日志格式字符串
        console_output: 是否输出到控制台（默认 False，只写文件）

    Returns:
        配置好的日志记录器
    """
    # 获取 code_agent 的根日志记录器
    logger = logging.getLogger("code_agent")
    logger.setLevel(getattr(logging, level))

    # 清除已有的处理器，避免重复添加
    logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(format_string)

    # 如果启用控制台输出，添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 添加文件处理器
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器。

    Args:
        name: 日志记录器名称，通常使用模块名

    Returns:
        日志记录器实例
    """
    return logging.getLogger(f"code_agent.{name}")
