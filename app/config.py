"""
config.py — 应用配置管理

使用 JSON 文件持久化用户偏好（窗口大小、主题、字体等）。
配置文件存储在用户目录下：~/.md-reader/config.json
"""

from __future__ import annotations

import json
import os
from typing import Any

# 默认配置
_DEFAULTS: dict[str, Any] = {
    "theme": "light",
    "font_size": 14,
    "editor_font_family": "Consolas",
    "preview_font_size": 16,
    "window_width": 1280,
    "window_height": 800,
    "window_x": 100,
    "window_y": 100,
    "last_folder": "",
    "show_file_tree": True,
    "show_toc": True,
    "scroll_sync": True,
    "render_delay_ms": 300,
    "tab_width": 4,
}

_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".md-reader")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "config.json")


class Config:
    """应用配置管理器（单例）"""

    _instance: Config | None = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = dict(_DEFAULTS)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """从磁盘加载配置"""
        try:
            if os.path.exists(_CONFIG_FILE):
                with open(_CONFIG_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                # 合并：保留默认值中新增的键
                for key, value in saved.items():
                    if key in self._data:
                        self._data[key] = value
        except (json.JSONDecodeError, OSError):
            pass  # 配置损坏时使用默认值

    def save(self) -> None:
        """持久化到磁盘"""
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass  # 写入失败时静默忽略

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def reset(self) -> None:
        self._data = dict(_DEFAULTS)
        self.save()
