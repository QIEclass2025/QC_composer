from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QMessageBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from PyQt6.QtGui import (
    QColor,
    QPen,
    QPainter,
    QFont,
)
from PyQt6.QtCore import Qt, QPointF


# ====== 회로 설정 ======
N_QUBITS = 3
CELL_WIDTH = 80
ROW_HEIGHT = 100
X_OFFSET = 50
Y_OFFSET = 70
PALETTE_OFFSET = 80


@dataclass
class GateInfo:
    gate_type: str
    row: int
    col: int


# ============================================================================
#  GateItem (UI + Snap + Hover + Selection)
# ============================================================================
class GateItem(QGraphicsRectItem):
    WIDTH = 60
    HEIGHT = 42
    RADIUS = 8

    def __init__(self, label: str, gate_type: str, circuit_view: "CircuitView"):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)

        self.label = label
        self.gate_type = gate_type
        self.circuit_view = circuit_view

        self.row: Optional[int] = None
        self.col: Optional[int] = None

        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.color_normal = QColor("#7EC8E3")
        self.color_hover = QColor("#9EDBFF")
        self.color_selected = QColor("#5EAAD5")

        # 텍스트
        self.text_item = QGraphicsTextItem(self)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(Qt.GlobalColor.black)
        self.text_item.setPlainText(self.label)
        self._center_text()

    def _center_text(self):
        rect = self.rect()
        t = self.text_item.boundingRect()
        self.text_item.setPos(
            (rect.width() - t.width()) / 2,
            (rect.height() - t.height()) / 2,
        )

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        if self.isSelected():
            painter.setBrush(self.color_selected)
        else:
            painter.setBrush(self.color_normal)

        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(r, self.RADIUS, self.RADIUS)

    def hoverEnterEvent(self, event):
        self.color_normal = self.color_hover
        self.update()

    def hoverLeaveEvent(self, event):
        self.color_normal = QColor("#7EC8E3")
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.circuit_view.snap_gate(self)
        self._center_text()


# ============================================================================
#  CircuitView
# ============================================================================
class CircuitView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setSceneRect(0, 0, 1200, 500)

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.circuit: Dict[Tuple[int, int], GateItem] = {}

        self._draw_wires()

    def _draw_wires(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        for i in range(N_QUBITS):
            y = Y_OFFSET + i * ROW_HEIGHT
            self.scene.addLine(X_OFFSET, y, 1000, y, pen)

    def add_gate(self, gate_type: str, label: str):
        gate = GateItem(label, gate_type, self)
        gate.setPos(
            QPointF(
                X_OFFSET + CELL_WIDTH * 0.2,
                Y_OFFSET - PALETTE_OFFSET
            )
        )
        self.scene.addItem(gate)

    def snap_gate(self, gate: GateItem):
        cx = gate.pos().x() + gate.WIDTH / 2
        cy = gate.pos().y() + gate.HEIGHT / 2

        # 팔레트 영역 → snap X
        if cy < Y_OFFSET - ROW_HEIGHT * 0.5:
            if gate.row is not None:
                self.circuit.pop((gate.row, gate.col), None)
                gate.row, gate.col = None, None
            return

        col = round((cx - X_OFFSET) / CELL_WIDTH)
        row = round((cy - Y_OFFSET) / ROW_HEIGHT)

        col = max(0, col)
        row = max(0, min(N_QUBITS - 1, row))

        nx = X_OFFSET + col * CELL_WIDTH - gate.WIDTH / 2
        ny = Y_OFFSET + row * ROW_HEIGHT - gate.HEIGHT / 2

        key_new = (row, col)
        key_old = (gate.row, gate.col)

        if key_old in self.circuit:
            del self.circuit[key_old]

        if key_new in self.circuit and self.circuit[key_new] is not gate:
            if key_old is not None:
                ox = X_OFFSET + key_old[1] * CELL_WIDTH - gate.WIDTH / 2
                oy = Y_OFFSET + key_old[0] * ROW_HEIGHT - gate.HEIGHT / 2
                gate.setPos(ox, oy)
                self.circuit[key_old] = gate
                return
            return

        self.circuit[key_new] = gate
        gate.row, gate.col = row, col
        gate.setPos(nx, ny)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            for item in list(self.scene.selectedItems()):
                if isinstance(item, GateItem):
                    if item.row is not None:
                        self.circuit.pop((item.row, item.col), None)
                    self.scene.removeItem(item)
        else:
            super().keyPressEvent(event)

    def export_gate_infos(self) -> List[GateInfo]:
        lst = []
        for (r, c), g in self.circuit.items():
            lst.append(GateInfo(g.gate_type, r, c))
        return sorted(lst, key=lambda x: (x.col, x.row))


# ============================================================================
#  MainWindow
# ============================================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quantum Circuit Composer (PyQt6)")

        layout = QHBoxLayout(self)

        # ---------- Palette ----------
        panel = QVBoxLayout()
        layout.addLayout(panel)

        btn_h = QPushButton("H Gate")
        btn_x = QPushButton("X Gate")
        btn_z = QPushButton("Z Gate")
        btn_c_ctrl = QPushButton("CNOT ●")
        btn_c_tgt = QPushButton("CNOT ⊕")

        panel.addWidget(btn_h)
        panel.addWidget(btn_x)
        panel.addWidget(btn_z)
        panel.addWidget(btn_c_ctrl)
        panel.addWidget(btn_c_tgt)

        panel.addSpacing(25)

        btn_export = QPushButton("Export to Qiskit")
        panel.addWidget(btn_export)
        panel.addStretch()

        # ---------- Canvas ----------
        self.view = CircuitView()
        layout.addWidget(self.view, stretch=1)

        btn_h.clicked.connect(lambda: self.view.add_gate("H", "H"))
        btn_x.clicked.connect(lambda: self.view.add_gate("X", "X"))
        btn_z.clicked.connect(lambda: self.view.add_gate("Z", "Z"))
        btn_c_ctrl.clicked.connect(lambda: self.view.add_gate("CNOT_CTRL", "●"))
        btn_c_tgt.clicked.connect(lambda: self.view.add_gate("CNOT_TGT", "⊕"))

        btn_export.clicked.connect(self._export_qiskit)

    # --------------------------------------------------------------
    # Qiskit Export
    # --------------------------------------------------------------
    def _export_qiskit(self):
        try:
            from qiskit import QuantumCircuit
        except:
            QMessageBox.warning(self, "Error", "Qiskit이 없습니다.\nuv add qiskit")
            return

        gates = self.view.export_gate_infos()
        qc = QuantumCircuit(N_QUBITS)

        by_col: Dict[int, List[GateInfo]] = {}
        for g in gates:
            by_col.setdefault(g.col, []).append(g)

        for col in sorted(by_col.keys()):
            ops = by_col[col]

            singles = [g for g in ops if g.gate_type in ("H", "X", "Z")]
            ctrls = [g for g in ops if g.gate_type == "CNOT_CTRL"]
            tgts  = [g for g in ops if g.gate_type == "CNOT_TGT"]

            for s in singles:
                if s.gate_type == "H":
                    qc.h(s.row)
                elif s.gate_type == "X":
                    qc.x(s.row)
                elif s.gate_type == "Z":
                    qc.z(s.row)

            k = min(len(ctrls), len(tgts))
            for i in range(k):
                qc.cx(ctrls[i].row, tgts[i].row)

        QMessageBox.information(self, "Qiskit Export", str(qc))


# ============================================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 650)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
