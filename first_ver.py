from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QLabel, QTabWidget
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QBrush
from PyQt6.QtCore import Qt, QRectF


# ============================================
# Global configs
# ============================================
N_QUBITS = 3
MAX_QUBITS = 8

CELL_WIDTH = 55
ROW_HEIGHT = 85

X_OFFSET = 80
Y_OFFSET = 90
PALETTE_OFFSET = 60

# 회로 가로 길이: 게이트 17칸
MAX_COLS = 17


@dataclass
class GateInfo:
    gate_type: str
    row: int
    col: int
    angle: Optional[float] = None


# ============================================
# GateItem
# ============================================
class GateItem(QGraphicsRectItem):
    WIDTH = 45
    HEIGHT = 32
    RADIUS = 6

    def __init__(self, label: str, gate_type: str, view: "CircuitView"):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)

        self.label = label
        self.gate_type = gate_type
        self.view = view

        self.row: Optional[int] = None
        self.col: Optional[int] = None

        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        font = QFont("Segoe UI", 10, QFont.Weight.Bold)

        self.text_item = QGraphicsTextItem(self)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(Qt.GlobalColor.black)
        self.text_item.setPlainText(label)

        self._center()

    def _center(self):
        r = self.rect()
        t = self.text_item.boundingRect()
        self.text_item.setPos(
            (r.width() - t.width()) / 2,
            (r.height() - t.height()) / 2,
        )

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.view.snap_gate(self)
        self._center()

    def paint(self, p: QPainter, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#5EAAD5") if self.isSelected() else QColor("#7EC8E3")
        p.setBrush(color)
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)


# ============================================
# CircuitView
# ============================================
class CircuitView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # 선/레이블만 살짝 왼쪽으로 밀기
        self.WIRE_SHIFT = -30

        # 가로 스크롤: 창이 작을 때만 자동 (옵션 B)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # 세로 스크롤: 큐빗 많아지면 자동
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.n_qubits = N_QUBITS
        self.circuit: Dict[Tuple[int, int], GateItem] = {}

        self.palette_gate: Optional[GateItem] = None
        self.connection_lines: List = []

        self._update_scene_rect()
        self._draw_all()

    # --- 회로 오른쪽 끝 x좌표 ---
    def get_right_end(self) -> float:
        return X_OFFSET + CELL_WIDTH * MAX_COLS

    # --- Scene 높이 동적 계산 ---
    def _compute_scene_height(self) -> float:
        # 큐빗 수 + classical 줄 + 여유
        return Y_OFFSET + (self.n_qubits + 1) * ROW_HEIGHT + 200

    def _update_scene_rect(self):
        right = self.get_right_end()
        height = self._compute_scene_height()
        self.setSceneRect(0, 0, right + 200, height)
        self.trash_rect = QRectF(right - 90, 10, 70, 60)

    # --- GateItem 제외하고 다 지우기 ---
    def _remove_non_gate_items(self):
        for it in list(self.scene.items()):
            # GateItem은 유지
            if isinstance(it, GateItem):
                continue
            # GateItem 안에 붙어 있는 텍스트도 유지
            if isinstance(it, QGraphicsTextItem) and isinstance(it.parentItem(), GateItem):
                continue
            self.scene.removeItem(it)

    # --- 전체 다시 그리기 ---
    def _draw_all(self):
        # 팔레트 게이트는 한 번 제거
        if self.palette_gate is not None:
            try:
                self.scene.removeItem(self.palette_gate)
            except RuntimeError:
                pass
            self.palette_gate = None

        # 게이트는 유지하면서 나머지만 제거
        self._remove_non_gate_items()

        # 와이어 + Trash 다시 그림
        self._draw_wires()
        self._draw_trash()

        # 회로 게이트 재배치 (이미 scene 안에 살아있음)
        for (r, c), g in list(self.circuit.items()):
            if r >= self.n_qubits:
                self.scene.removeItem(g)
                self.circuit.pop((r, c))
            else:
                x = X_OFFSET + c * CELL_WIDTH - g.WIDTH / 2
                y = Y_OFFSET + r * ROW_HEIGHT - g.HEIGHT / 2
                g.setPos(x, y)

        # CTRL–Target 연결선
        self._draw_connections()

    # --- 와이어 & 레이블 ---
    def _draw_wires(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        right = self.get_right_end()

        # quantum wires
        for i in range(self.n_qubits):
            y = Y_OFFSET + i * ROW_HEIGHT
            self.scene.addLine(
                X_OFFSET + self.WIRE_SHIFT,
                y,
                right + self.WIRE_SHIFT,
                y,
                pen,
            )
            txt = QGraphicsTextItem(f"q[{i}]")
            txt.setFont(QFont("Segoe UI", 11))
            txt.setDefaultTextColor(Qt.GlobalColor.black)
            txt.setPos(X_OFFSET + self.WIRE_SHIFT - 40, y - 10)
            self.scene.addItem(txt)

        # classical wire
        y2 = Y_OFFSET + self.n_qubits * ROW_HEIGHT
        self.scene.addLine(
            X_OFFSET + self.WIRE_SHIFT,
            y2,
            right + self.WIRE_SHIFT,
            y2,
            pen,
        )
        txt = QGraphicsTextItem(f"c({self.n_qubits})")
        txt.setFont(QFont("Segoe UI", 12))
        txt.setDefaultTextColor(Qt.GlobalColor.black)
        txt.setPos(X_OFFSET + self.WIRE_SHIFT - 40, y2 - 10)
        self.scene.addItem(txt)

    # --- Trash ---
    def _draw_trash(self):
        pen = QPen(Qt.GlobalColor.black)
        brush = QBrush(QColor("#FFDDDD"))
        self.scene.addRect(self.trash_rect, pen, brush)

        t = QGraphicsTextItem("🗑")
        t.setFont(QFont("Segoe UI", 20))
        t.setDefaultTextColor(Qt.GlobalColor.black)
        t.setPos(self.trash_rect.x() + 18, self.trash_rect.y() + 8)
        self.scene.addItem(t)

    # --- CTRL–Target 연결선 ---
    def _draw_connections(self):
        for line in self.connection_lines:
            self.scene.removeItem(line)
        self.connection_lines.clear()

        bycol: Dict[int, List[GateItem]] = {}
        for (r, c), g in self.circuit.items():
            bycol.setdefault(c, []).append(g)

        for col, gates in bycol.items():
            ctrls = [g for g in gates if g.gate_type == "CTRL"]
            xt = [g for g in gates if g.gate_type == "X_T"]
            zt = [g for g in gates if g.gate_type == "Z_T"]
            targets = xt + zt

            if len(targets) != 1:
                continue

            tgt = targets[0]
            tx = tgt.pos().x() + tgt.WIDTH / 2
            ty = tgt.pos().y() + tgt.HEIGHT / 2

            for ctrl in ctrls:
                cx = ctrl.pos().x() + ctrl.WIDTH / 2
                cy = ctrl.pos().y() + ctrl.HEIGHT / 2
                pen = QPen(Qt.GlobalColor.black)
                pen.setWidth(2)
                line = self.scene.addLine(cx, cy, tx, ty, pen)
                line.setZValue(-1)
                self.connection_lines.append(line)

    # --- 팔레트 게이트 생성 ---
    def set_palette_gate(self, gate_type: str, label: str):
        if self.palette_gate is not None:
            try:
                self.scene.removeItem(self.palette_gate)
            except RuntimeError:
                pass
            self.palette_gate = None

        g = GateItem(label, gate_type, self)

        center = self.viewport().rect().center()
        sc = self.mapToScene(center)
        g.setPos(sc.x() - g.WIDTH / 2, Y_OFFSET - PALETTE_OFFSET)

        self.palette_gate = g
        self.scene.addItem(g)

    # --- 스냅 동작 ---
    def snap_gate(self, g: GateItem):
        cx = g.pos().x() + g.WIDTH / 2
        cy = g.pos().y() + g.HEIGHT / 2

        # Trash에 떨어지면 삭제
        if self.trash_rect.contains(cx, cy):
            if g.row is not None:
                self.circuit.pop((g.row, g.col), None)
            if g is self.palette_gate:
                self.palette_gate = None
            self.scene.removeItem(g)
            self._draw_connections()
            return

        # 팔레트 영역(위쪽): 회로에서 제거만 하고 위에 떠 있게 둠
        if cy < Y_OFFSET - ROW_HEIGHT * 0.5:
            if g.row is not None:
                self.circuit.pop((g.row, g.col), None)
                g.row = g.col = None
            self._draw_connections()
            return

        # 회로 격자 스냅
        col = round((cx - X_OFFSET) / CELL_WIDTH)
        row = round((cy - Y_OFFSET) / ROW_HEIGHT)

        col = max(0, min(col, MAX_COLS - 1))
        row = max(0, min(row, self.n_qubits - 1))

        nx = X_OFFSET + col * CELL_WIDTH - g.WIDTH / 2
        ny = Y_OFFSET + row * ROW_HEIGHT - g.HEIGHT / 2

        old_key = (g.row, g.col) if g.row is not None else None
        new_key = (row, col)

        if old_key in self.circuit:
            self.circuit.pop(old_key, None)

        # 이미 그 칸에 다른 게이트 있으면 이전 위치 복원
        if new_key in self.circuit and self.circuit[new_key] is not g:
            if old_key:
                ox = X_OFFSET + old_key[1] * CELL_WIDTH - g.WIDTH / 2
                oy = Y_OFFSET + old_key[0] * ROW_HEIGHT - g.HEIGHT / 2
                g.setPos(ox, oy)
                self.circuit[old_key] = g
            self._draw_connections()
            return

        self.circuit[new_key] = g
        g.row, g.col = row, col
        g.setPos(nx, ny)

        if g is self.palette_gate:
            self.palette_gate = None

        self._draw_connections()

    # --- Delete 키로 게이트 삭제 ---
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete:
            for it in list(self.scene.selectedItems()):
                if isinstance(it, GateItem):
                    if it.row is not None:
                        self.circuit.pop((it.row, it.col), None)
                    if it is self.palette_gate:
                        self.palette_gate = None
                    self.scene.removeItem(it)
            self._draw_connections()
        else:
            super().keyPressEvent(e)

    # --- Export용 정보 ---
    def export_gate_infos(self) -> List[GateInfo]:
        out: List[GateInfo] = []
        for (r, c), g in self.circuit.items():
            angle = None
            if g.gate_type in ("RX", "RY", "RZ"):
                angle = 3.141592653589793 / 2
            out.append(GateInfo(g.gate_type, r, c, angle))
        return sorted(out, key=lambda x: (x.col, x.row))


# ============================================
# Tutorial Tab
# ============================================
class TutorialTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        lbl = QLabel("Quantum Algorithm Tutorial (준비 중)")
        lbl.setFont(QFont("Segoe UI", 12))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)


# ============================================
# Composer Tab
# ============================================
class ComposerTab(QWidget):
    def __init__(self):
        super().__init__()

        main = QHBoxLayout(self)

        panel = QVBoxLayout()
        main.addLayout(panel)

        def add_btn(text: str, gate_type: str, label: str):
            btn = QPushButton(text)
            btn.setFont(QFont("Segoe UI", 10))
            btn.clicked.connect(lambda: self.select_gate(gate_type, label))
            panel.addWidget(btn)

        add_btn("● Control", "CTRL", "●")
        add_btn("⊕ X Target", "X_T", "⊕")
        add_btn("⊙ Z Target", "Z_T", "⊙")

        panel.addSpacing(10)
        add_btn("H", "H", "H")
        add_btn("X", "X", "X")
        add_btn("Y", "Y", "Y")
        add_btn("Z", "Z", "Z")

        panel.addSpacing(10)
        add_btn("Rx", "RX", "Rx")
        add_btn("Ry", "RY", "Ry")
        add_btn("Rz", "RZ", "Rz")

        panel.addSpacing(10)
        add_btn("M (Measurement)", "MEASURE", "M")

        panel.addSpacing(10)
        btn_add = QPushButton("Add Qubit")
        btn_del = QPushButton("Delete Qubit")
        panel.addWidget(btn_add)
        panel.addWidget(btn_del)

        panel.addSpacing(10)
        btn_export = QPushButton("Export to Qiskit")
        panel.addWidget(btn_export)

        panel.addSpacing(20)

        self.desc = QLabel("게이트 설명")
        self.desc.setWordWrap(True)
        panel.addWidget(self.desc)
        panel.addStretch()

        self.view = CircuitView()
        main.addWidget(self.view, stretch=1)

        btn_add.clicked.connect(self.add_q)
        btn_del.clicked.connect(self.del_q)
        btn_export.clicked.connect(self.export_qiskit)

        self.gate_desc = {
            "CTRL": "Control gate (●): Target(⊕/⊙)을 제어.",
            "X_T": "X Target (⊕): CTRL과 함께 CNOT/MCX.",
            "Z_T": "Z Target (⊙): CTRL과 함께 CZ/MCZ.",
            "H": "Hadamard gate.",
            "X": "Pauli-X gate.",
            "Y": "Pauli-Y gate.",
            "Z": "Pauli-Z gate.",
            "RX": "Rx(θ) rotation.",
            "RY": "Ry(θ) rotation.",
            "RZ": "Rz(θ) rotation.",
            "MEASURE": "Measurement gate.",
        }

    # --- 게이트 선택 ---
    def select_gate(self, gate_type: str, label: str):
        self.view.set_palette_gate(gate_type, label)
        self.desc.setText(self.gate_desc.get(gate_type, gate_type))

    # --- Qubit 추가 ---
    def add_q(self):
        if self.view.n_qubits >= MAX_QUBITS:
            QMessageBox.warning(self, "Limit", "최대 8개의 큐빗까지 가능합니다.")
            return
        self.view.n_qubits += 1
        self.view._update_scene_rect()
        self.view._draw_all()

    # --- Qubit 삭제 ---
    def del_q(self):
        if self.view.n_qubits <= 1:
            QMessageBox.warning(self, "Limit", "최소 1개의 큐빗은 필요합니다.")
            return

        remove_row = self.view.n_qubits - 1

        for (r, c), g in list(self.view.circuit.items()):
            if r == remove_row:
                self.view.scene.removeItem(g)
                self.view.circuit.pop((r, c))

        self.view.n_qubits -= 1
        self.view._update_scene_rect()
        self.view._draw_all()

    # --- Qiskit Export ---
    def export_qiskit(self):
        try:
            from qiskit import QuantumCircuit
        except Exception:
            QMessageBox.warning(self, "Error", "Qiskit이 설치되어 있지 않습니다.\nuv add qiskit")
            return

        infos = self.view.export_gate_infos()
        qc = QuantumCircuit(self.view.n_qubits, self.view.n_qubits)

        bycol: Dict[int, List[GateInfo]] = {}
        for g in infos:
            bycol.setdefault(g.col, []).append(g)

        try:
            for col in sorted(bycol.keys()):
                ops = bycol[col]

                # 단일 게이트
                for g in ops:
                    if g.gate_type == "H":
                        qc.h(g.row)
                    elif g.gate_type == "X":
                        qc.x(g.row)
                    elif g.gate_type == "Y":
                        qc.y(g.row)
                    elif g.gate_type == "Z":
                        qc.z(g.row)
                    elif g.gate_type == "RX":
                        qc.rx(g.angle, g.row)
                    elif g.gate_type == "RY":
                        qc.ry(g.angle, g.row)
                    elif g.gate_type == "RZ":
                        qc.rz(g.angle, g.row)

                ctrls = [g for g in ops if g.gate_type == "CTRL"]
                xt = [g for g in ops if g.gate_type == "X_T"]
                zt = [g for g in ops if g.gate_type == "Z_T"]
                targets = xt + zt

                if len(targets) > 1:
                    raise ValueError(f"column {col}: Target(X_T/Z_T)는 한 개만 가능합니다.")

                # X target
                if len(xt) == 1:
                    tgt = xt[0].row
                    if len(ctrls) == 0:
                        qc.x(tgt)
                    elif len(ctrls) == 1:
                        qc.cx(ctrls[0].row, tgt)
                    else:
                        qc.mcx([c.row for c in ctrls], tgt)

                # Z target
                if len(zt) == 1:
                    tgt = zt[0].row
                    if len(ctrls) == 0:
                        qc.z(tgt)
                    elif len(ctrls) == 1:
                        qc.cz(ctrls[0].row, tgt)
                    else:
                        qc.mcz([c.row for c in ctrls], tgt)

                # 측정
                for g in ops:
                    if g.gate_type == "MEASURE":
                        qc.measure(g.row, g.row)

        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Qiskit 회로 생성 중 오류:\n{e}")
            return

        QMessageBox.information(self, "Qiskit Export", str(qc))


# ============================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(TutorialTab(), "Tutorial")
        tabs.addTab(ComposerTab(), "Circuit Composer")

        self.setWindowTitle("Quantum Circuit Composer")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1300, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
