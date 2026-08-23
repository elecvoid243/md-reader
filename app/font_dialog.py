"""
font_dialog.py — 字体设置对话框

统一配置三种视图的字体：
- 预览正文 / 等宽字体 + 字号（阅读模式与即时渲染共用，CSS 变量覆盖）
- 源码编辑器字体 + 字号

字体家族留空（"跟随主题"）表示不覆盖主题默认字体栈。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# 各控件的默认值（与 config.py / 主题默认保持一致）
_DEFAULT_BODY_FAMILY = ""
_DEFAULT_MONO_FAMILY = ""
_DEFAULT_PREVIEW_SIZE = 16
_DEFAULT_EDITOR_FAMILY = "Consolas"
_DEFAULT_EDITOR_SIZE = 14


def _system_families() -> List[str]:
    try:
        return sorted(set(QFontDatabase().families()))
    except Exception:
        return []


class FontSettingsDialog(QDialog):
    """字体设置对话框：确定后通过 values() 取结果（family 为空表示跟随主题）"""

    def __init__(self, preview_family: str, preview_heading: str,
                 preview_mono: str, preview_size: int,
                 editor_family: str, editor_size: int,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("字体设置")

        root = QVBoxLayout(self)

        # ── 预览（阅读 / 即时渲染） ──
        preview_box = QGroupBox("预览（阅读模式 / 即时渲染）")
        preview_form = QFormLayout(preview_box)

        self._body_combo = self._make_combo(preview_family)
        preview_form.addRow("正文字体：", self._body_combo)

        self._heading_combo = self._make_combo(preview_heading)
        preview_form.addRow("标题字体：", self._heading_combo)

        self._preview_size = QSpinBox()
        self._preview_size.setRange(10, 32)
        self._preview_size.setValue(preview_size or _DEFAULT_PREVIEW_SIZE)
        preview_form.addRow("字号：", self._preview_size)

        self._mono_combo = self._make_combo(preview_mono)
        preview_form.addRow("等宽字体（代码）：", self._mono_combo)
        root.addWidget(preview_box)

        # ── 源码编辑器 ──
        editor_box = QGroupBox("源码编辑器")
        editor_form = QFormLayout(editor_box)

        self._editor_combo = self._make_combo(editor_family, allow_default=False)
        editor_form.addRow("字体：", self._editor_combo)

        self._editor_size = QSpinBox()
        self._editor_size.setRange(8, 28)
        self._editor_size.setValue(editor_size or _DEFAULT_EDITOR_SIZE)
        editor_form.addRow("字号：", self._editor_size)
        root.addWidget(editor_box)

        # ── 底部按钮 ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._reset_defaults)

        btn_row = QHBoxLayout()
        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(buttons)
        root.addLayout(btn_row)

        self.setMinimumWidth(380)

    def _make_combo(self, family: str, allow_default: bool = True) -> QComboBox:
        """字体选择框；allow_default 时提供"跟随主题"空选项。

        不用 QFontComboBox：它会在构造/显示时自行重填字体模型
        （含大量空条目），与手工添加的选项互相冲突，
        currentData 也拿不到自定义数据。
        """
        combo = QComboBox()
        if allow_default:
            combo.addItem("（跟随主题）", "")
        for f in _system_families():
            combo.addItem(f, f)
        # 当前值不在系统字体列表时（如换过机器）补入，保证不丢失
        if family:
            idx = combo.findText(family)
            if idx < 0:
                combo.insertItem(1 if allow_default else 0, family, family)
                idx = combo.findText(family)
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)
        return combo

    def _reset_defaults(self) -> None:
        self._body_combo.setCurrentIndex(0)
        self._heading_combo.setCurrentIndex(0)
        self._mono_combo.setCurrentIndex(0)
        self._preview_size.setValue(_DEFAULT_PREVIEW_SIZE)
        idx = self._editor_combo.findText(_DEFAULT_EDITOR_FAMILY)
        if idx >= 0:
            self._editor_combo.setCurrentIndex(idx)
        self._editor_size.setValue(_DEFAULT_EDITOR_SIZE)

    def values(self) -> Tuple[str, str, str, int, str, int]:
        """返回 (正文字体, 标题字体, 等宽字体, 预览字号, 编辑器字体, 编辑器字号)"""
        return (
            self._body_combo.currentData() or "",
            self._heading_combo.currentData() or "",
            self._mono_combo.currentData() or "",
            self._preview_size.value(),
            self._editor_combo.currentText(),
            self._editor_size.value(),
        )
