from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QLabel, QTabWidget, QDialog, QTextEdit,
    QSplitter, QScrollArea, QListWidget, QListWidgetItem # QSplitter, QScrollArea, QListWidget 추가
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QBrush
from PyQt6.QtCore import Qt, QRectF

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


# ============================================
# CONFIG
# ============================================
N_QUBITS = 3
MAX_QUBITS = 8

CELL_WIDTH = 55
ROW_HEIGHT = 85

X_OFFSET = 80
Y_OFFSET = 90
PALETTE_OFFSET = 60

MAX_COLS = 17


@dataclass
class GateInfo:
    gate_type: str
    row: int
    col: int
    angle: Optional[float] = None


# ============================================
# Gate item UI
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
        self.text_item.setPos((r.width() - t.width())/2, (r.height()-t.height())/2)

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
# Circuit View
# ============================================
class CircuitView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.WIRE_SHIFT = -30
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.n_qubits = N_QUBITS
        self.circuit: Dict[Tuple[int, int], GateItem] = {}
        self.palette_gate: Optional[GateItem] = None
        self.connection_lines: List = []

        self._update_scene_rect()
        self._draw_all()

    def get_right_end(self) -> float:
        return X_OFFSET + CELL_WIDTH * MAX_COLS

    def _compute_scene_height(self):
        return Y_OFFSET + (self.n_qubits + 1)*ROW_HEIGHT + 200

    def _update_scene_rect(self):
        right = self.get_right_end()
        height = self._compute_scene_height()
        self.setSceneRect(0, 0, right+200, height)
        self.trash_rect = QRectF(right - 90, 10, 70, 60)

    def _draw_all(self):
        # palette 제거
        if self.palette_gate is not None:
            self.scene.removeItem(self.palette_gate)
            self.palette_gate = None

        # 기존 장식 제거
        for it in list(self.scene.items()):
            if isinstance(it, GateItem):
                continue
            if isinstance(it, QGraphicsTextItem) and isinstance(it.parentItem(), GateItem):
                continue
            self.scene.removeItem(it)

        # wires
        self._draw_wires()
        self._draw_trash()

        # placed gates
        for (r,c), g in list(self.circuit.items()):
            if r >= self.n_qubits:
                self.scene.removeItem(g)
                del self.circuit[(r,c)]
            else:
                x = X_OFFSET + c*CELL_WIDTH - g.WIDTH/2
                y = Y_OFFSET + r*ROW_HEIGHT - g.HEIGHT/2
                g.setPos(x,y)

        self._draw_connections()

    def _draw_wires(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        right = self.get_right_end()

        for i in range(self.n_qubits):
            y = Y_OFFSET + i*ROW_HEIGHT
            self.scene.addLine(
                X_OFFSET+self.WIRE_SHIFT, y,
                right+self.WIRE_SHIFT, y,
                pen,
            )
            lbl = QGraphicsTextItem(f"q[{i}]")
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setDefaultTextColor(Qt.GlobalColor.black)
            lbl.setPos(X_OFFSET+self.WIRE_SHIFT-40, y-10)
            self.scene.addItem(lbl)

        y2 = Y_OFFSET + self.n_qubits*ROW_HEIGHT
        self.scene.addLine(
            X_OFFSET+self.WIRE_SHIFT, y2,
            right+self.WIRE_SHIFT, y2,
            pen,
        )
        txt = QGraphicsTextItem(f"c({self.n_qubits})")
        txt.setFont(QFont("Segoe UI", 12))
        txt.setDefaultTextColor(Qt.GlobalColor.black)
        txt.setPos(X_OFFSET+self.WIRE_SHIFT-40, y2-10)
        self.scene.addItem(txt)

    def _draw_trash(self):
        pen = QPen(Qt.GlobalColor.black)
        brush = QBrush(QColor("#FFDDDD"))
        self.scene.addRect(self.trash_rect, pen, brush)
        t = QGraphicsTextItem("🗑")
        t.setFont(QFont("Segoe UI", 20))
        t.setDefaultTextColor(Qt.GlobalColor.black)
        t.setPos(self.trash_rect.x()+18, self.trash_rect.y()+8)
        self.scene.addItem(t)

    def _draw_connections(self):
        for l in self.connection_lines:
            self.scene.removeItem(l)
        self.connection_lines.clear()

        bycol: Dict[int, List[GateItem]] = {}
        for (r,c), g in self.circuit.items():
            bycol.setdefault(c, []).append(g)

        for col, ops in bycol.items():
            ctrls = [g for g in ops if g.gate_type=="CTRL"]
            tgt   = [g for g in ops if g.gate_type in ("X_T","Z_T")]

            if len(tgt) != 1:
                continue

            tg = tgt[0]
            tx = tg.pos().x()+tg.WIDTH/2
            ty = tg.pos().y()+tg.HEIGHT/2

            for c in ctrls:
                cx = c.pos().x()+c.WIDTH/2
                cy = c.pos().y()+c.HEIGHT/2
                pen = QPen(Qt.GlobalColor.black)
                pen.setWidth(2)
                line = self.scene.addLine(cx,cy,tx,ty,pen)
                line.setZValue(-1)
                self.connection_lines.append(line)

    def set_palette_gate(self, gate_type, label):
        if self.palette_gate:
            self.scene.removeItem(self.palette_gate)
            self.palette_gate = None

        g = GateItem(label, gate_type, self)
        sc = self.mapToScene(self.viewport().rect().center())
        g.setPos(sc.x()-g.WIDTH/2, Y_OFFSET-PALETTE_OFFSET)
        self.palette_gate = g
        self.scene.addItem(g)

    def snap_gate(self, g: GateItem):
        cx = g.pos().x()+g.WIDTH/2
        cy = g.pos().y()+g.HEIGHT/2

        # trash
        if self.trash_rect.contains(cx,cy):
            if g.row!=None:
                self.circuit.pop((g.row,g.col), None)
            self.scene.removeItem(g)
            self.palette_gate = None
            self._draw_connections()
            return

        # palette 영역으로
        if cy < Y_OFFSET - 40:
            if g.row!=None:
                self.circuit.pop((g.row,g.col), None)
                g.row=g.col=None
            self._draw_connections()
            return

        col = round((cx-X_OFFSET)/CELL_WIDTH)
        row = round((cy-Y_OFFSET)/ROW_HEIGHT)

        col = max(0,min(col,MAX_COLS-1))
        row = max(0,min(row,self.n_qubits-1))

        nx = X_OFFSET+col*CELL_WIDTH - g.WIDTH/2
        ny = Y_OFFSET+row*ROW_HEIGHT - g.HEIGHT/2

        old = (g.row,g.col) if g.row!=None else None
        new = (row,col)

        if old in self.circuit:
            self.circuit.pop(old,None)

        if new in self.circuit and self.circuit[new] is not g:
            if old:
                ox = X_OFFSET+old[1]*CELL_WIDTH-g.WIDTH/2
                oy = Y_OFFSET+old[0]*ROW_HEIGHT-g.HEIGHT/2
                g.setPos(ox,oy)
                self.circuit[old]=g
            self._draw_connections()
            return

        self.circuit[new]=g
        g.row=row
        g.col=col
        g.setPos(nx,ny)

        if g is self.palette_gate:
            self.palette_gate=None

        self._draw_connections()

    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Delete:
            for it in list(self.scene.selectedItems()):
                if isinstance(it,GateItem):
                    if it.row!=None:
                        self.circuit.pop((it.row,it.col),None)
                    if it is self.palette_gate:
                        self.palette_gate=None
                    self.scene.removeItem(it)
            self._draw_connections()
        else:
            super().keyPressEvent(e)

    def export_gate_infos(self)->List[GateInfo]:
        out=[]
        for (r,c),g in self.circuit.items():
            ang=None
            if g.gate_type in ("RX","RY","RZ"):
                ang=3.141592653589793/2
            out.append(GateInfo(g.gate_type,r,c,ang))
        return sorted(out,key=lambda x:(x.col,x.row))


# ============================================
# Tutorial Tab (with split screen)
# ============================================
class TutorialTab(QWidget):
    # 튜토리얼 데이터 정의 (생략)
    TUTORIAL_DATA = {
        "1. Qubit과 Hadamard Gate": 
            "## Qubit과 Hadamard Gate\n\n"
            "**1. Qubit (양자 비트):** 고전적인 비트(0 또는 1)와 달리, 큐비트는 $\\left|0\\right\\rangle$과 $\\left|1\\right\\rangle$ 상태의 **중첩(Superposition)** 상태를 가질 수 있습니다. 이는 동시에 여러 값을 나타낼 수 있음을 의미하며, 계산의 병렬성을 부여합니다.\n\n"
            "**2. Hadamard (H) Gate:** 이 게이트는 큐비트를 순수한 $\\left|0\\right\\rangle$ 또는 $\\left|1\\right\\rangle$ 상태에서 완벽한 중첩 상태로 만듭니다. 회로에 H 게이트를 추가하고 Run Measurement를 실행하여 결과를 확인해 보세요.",
        
        "2. CNOT과 Entanglement": 
            "## CNOT과 Entanglement (얽힘)\n\n"
            "**1. CNOT (Controlled-X):** 이 게이트는 두 큐비트에 작용합니다. 제어 큐비트(Control, '●')가 $\\left|1\\right\\rangle$일 때만 대상 큐비트(Target, '⊕')에 X(NOT) 연산을 적용합니다. 만약 제어 큐비트가 $\\left|0\\right\\rangle$이면 아무 일도 하지 않습니다.\n\n"
            "**2. Entanglement (얽힘):** Qubit 0에 H 게이트를 적용한 다음, Qubit 0을 제어 큐비트로, Qubit 1을 대상 큐비트로 하는 CNOT 게이트를 적용해 보세요. 이 상태에서 두 큐비트는 **얽힘 상태(Bell State)**가 됩니다. 이 상태에서는 한 큐비트를 측정하면 다른 큐비트의 상태가 즉시 결정됩니다.",
            
        "3. 양자 푸리에 변환 (QFT) 기초": 
            "## 양자 푸리에 변환 (QFT) 기초\n\n"
            "QFT는 Shor의 알고리즘과 같은 복잡한 양자 알고리즘의 핵심 구성 요소입니다. 이는 고전적인 이산 푸리에 변환(DFT)의 양자 버전이며, 중첩된 양자 상태에서 주파수 정보를 추출하는 데 사용됩니다.\n\n"
            "QFT는 주로 Hadamard 게이트와 조건부 위상 이동 게이트(Controlled Phase Shift Gate, Rz 게이트의 특정 형태)의 조합으로 구현됩니다. 3큐비트 QFT를 구성하여 그 효과를 실험해 보세요."
    }

    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)
        
        # 제목 추가
        title = QLabel("Quantum Circuit Composer - 튜토리얼")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # 제목과 분할 영역 사이의 간격을 줄입니다 (Stretch 제거 및 Spacing 조정)
        main_layout.setSpacing(5) 
        
        # 튜토리얼 목록과 내용 영역 분할
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1) # stretch=1로 설정하여 분할 영역이 공간을 최대한 차지하도록 함
        
        # ----------------------------------------
        # 왼쪽 1/4: 튜토리얼 목록 (스크롤 가능)
        # ----------------------------------------
        list_area = QWidget()
        list_layout = QVBoxLayout(list_area)
        
        # 스크롤 가능한 영역 설정
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        list_container = QWidget()
        self.tutorial_list_layout = QVBoxLayout(list_container)
        self.tutorial_list_layout.setContentsMargins(5, 5, 5, 5) # 목록 내부 여백 조정
        self.tutorial_list_layout.setSpacing(3) # 목록 버튼 간 간격 조정
        
        # 튜토리얼 버튼 동적 생성
        for title_key in self.TUTORIAL_DATA:
            btn = QPushButton(title_key)
            btn.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold)) 
            # 람다 함수를 사용하여 클릭 시 튜토리얼 내용을 표시하도록 연결
            btn.clicked.connect(lambda checked, key=title_key: self.display_tutorial(key))
            self.tutorial_list_layout.addWidget(btn)
            
        self.tutorial_list_layout.addStretch() # 버튼들을 상단에 정렬
        scroll.setWidget(list_container)
        
        list_layout.addWidget(scroll)
        
        # ----------------------------------------
        # 오른쪽 3/4: 튜토리얼 내용 표시 영역
        # ----------------------------------------
        self.content_display = QTextEdit()
        self.content_display.setReadOnly(True)
        self.content_display.setPlaceholderText("왼쪽 목록에서 튜토리얼을 선택하세요.")
        
        # 초기 튜토리얼 표시
        first_key = next(iter(self.TUTORIAL_DATA))
        self.display_tutorial(first_key)

        # QSplitter에 위젯 추가 및 비율 설정
        splitter.addWidget(list_area)
        splitter.addWidget(self.content_display)
        
        # 분할 비율을 조정하여 오른쪽 창을 더 넓게 만듭니다 (예: 1/5 지점)
        # [200, 800] 또는 [150, 600] 등의 비율로 설정합니다.
        # 현재 창 크기(1350)를 기준으로 1/5인 약 270 픽셀을 목록에 할당합니다.
        splitter.setSizes([270, 1080]) # 1:4 비율 (20% vs 80%)에 가깝게 조정
        
    def display_tutorial(self, key: str):
        """선택된 튜토리얼의 내용을 QTextEdit에 표시합니다."""
        content = self.TUTORIAL_DATA.get(key, "선택된 튜토리얼 내용을 찾을 수 없습니다.")
        
        # 마크다운 텍스트를 HTML 형식으로 변환하여 더 잘 표시할 수 있음 (선택적)
        html_content = self.markdown_to_html(content)
        self.content_display.setText(html_content)

    def markdown_to_html(self, markdown_text: str) -> str:
        """간단한 마크다운을 HTML로 변환합니다 (QTextEdit 렌더링용)."""
        html = markdown_text.replace('\n\n', '<br><br>')
        html = html.replace('## ', '<h2>')
        html = html.replace('**', '<b>')
        html = html.replace('</b> (', '</b> (')
        # LaTeX 식은 일반 텍스트로 남겨둡니다.
        return html
        

# ============================================
# Composer Tab
# ============================================
class ComposerTab(QWidget):
    def __init__(self):
        super().__init__()
        main=QHBoxLayout(self)

        panel=QVBoxLayout()
        main.addLayout(panel)

        # palette buttons
        def add_btn(text,gt,label):
            b=QPushButton(text)
            b.clicked.connect(lambda:self.select_gate(gt,label))
            panel.addWidget(b)

        add_btn("● Control","CTRL","●")
        add_btn("⊕ X Target","X_T","⊕")
        add_btn("⊙ Z Target","Z_T","⊙")
        panel.addSpacing(10)
        add_btn("H","H","H")
        add_btn("X","X","X")
        add_btn("Y","Y","Y")
        add_btn("Z","Z","Z")
        panel.addSpacing(10)
        add_btn("Rx","RX","Rx")
        add_btn("Ry","RY","Ry")
        add_btn("Rz","RZ","Rz")
        panel.addSpacing(10)
        add_btn("M","MEASURE","M")

        panel.addSpacing(10)
        btn_add=QPushButton("Add Qubit")
        btn_del=QPushButton("Delete Qubit")
        panel.addWidget(btn_add)
        panel.addWidget(btn_del)

        panel.addSpacing(15)
        self.btn_export=QPushButton("Export Qiskit Code")
        self.btn_measure=QPushButton("Run Measurement")
        panel.addWidget(self.btn_export)
        panel.addWidget(self.btn_measure)
        panel.addStretch()

        self.view=CircuitView()
        main.addWidget(self.view,stretch=1)

        btn_add.clicked.connect(self.add_q)
        btn_del.clicked.connect(self.del_q)
        self.btn_export.clicked.connect(self.export_qiskit)
        self.btn_measure.clicked.connect(self.run_measurement)

    # -----------------------------------------------------
    def select_gate(self,gt,label):
        self.view.set_palette_gate(gt,label)

    def add_q(self):
        if self.view.n_qubits>=MAX_QUBITS:
            QMessageBox.warning(self,"Limit","Max 8 qubits")
            return
        self.view.n_qubits+=1
        self.view._update_scene_rect()
        self.view._draw_all()

    def del_q(self):
        if self.view.n_qubits<=1:
            QMessageBox.warning(self,"Limit","At least 1 qubit")
            return

        remove_row=self.view.n_qubits-1
        for(k,g) in list(self.view.circuit.items()):
            if k[0]==remove_row:
                self.view.scene.removeItem(g)
                del self.view.circuit[k]
        self.view.n_qubits-=1
        self.view._update_scene_rect()
        self.view._draw_all()

    # -----------------------------------------------------
    # Build real qiskit circuit
    # -----------------------------------------------------
    def build_qiskit_circuit(self):
        infos=self.view.export_gate_infos()
        qc=QuantumCircuit(self.view.n_qubits,self.view.n_qubits)

        bycol={}
        for g in infos:
            bycol.setdefault(g.col,[]).append(g)

        for col in sorted(bycol):
            ops = bycol[col]

            # single-qubit ops
            for g in ops:
                if g.gate_type=="H": qc.h(g.row)
                elif g.gate_type=="X": qc.x(g.row)
                elif g.gate_type=="Y": qc.y(g.row)
                elif g.gate_type=="Z": qc.z(g.row)
                elif g.gate_type=="RX": qc.rx(g.angle,g.row)
                elif g.gate_type=="RY": qc.ry(g.angle,g.row)
                elif g.gate_type=="RZ": qc.rz(g.angle,g.row)

            ctrls=[g.row for g in ops if g.gate_type=="CTRL"]
            xt=[g.row for g in ops if g.gate_type=="X_T"]
            zt=[g.row for g in ops if g.gate_type=="Z_T"]

            if len(xt)==1:
                t=xt[0]
                if len(ctrls)==0: qc.x(t)
                elif len(ctrls)==1: qc.cx(ctrls[0],t)
                else: qc.mcx(ctrls,t)

            if len(zt)==1:
                t=zt[0]
                if len(ctrls)==0: qc.z(t)
                elif len(ctrls)==1: qc.cz(ctrls[0],t)
                else: qc.mcz(ctrls,t)

            for g in ops:
                if g.gate_type=="MEASURE":
                    qc.measure(g.row,g.row)

        return qc

    # -----------------------------------------------------
    # Export QISKIT CODE — SAFE VERSION
    # -----------------------------------------------------
    def export_qiskit(self):
        try:
            infos=self.view.export_gate_infos()
        except Exception as e:
            QMessageBox.warning(self,"Export Error",f"{e}")
            return

        code=[]
        code.append("from qiskit import QuantumCircuit\n")
        code.append(f"qc = QuantumCircuit({self.view.n_qubits}, {self.view.n_qubits})\n\n")

        # first pass: single-qubit
        for g in infos:
            if g.gate_type=="H": code.append(f"qc.h({g.row})\n")
            elif g.gate_type=="X": code.append(f"qc.x({g.row})\n")
            elif g.gate_type=="Y": code.append(f"qc.y({g.row})\n")
            elif g.gate_type=="Z": code.append(f"qc.z({g.row})\n")
            elif g.gate_type=="RX": code.append(f"qc.rx({g.angle}, {g.row})\n")
            elif g.gate_type=="RY": code.append(f"qc.ry({g.angle}, {g.row})\n")
            elif g.gate_type=="RZ": code.append(f"qc.rz({g.angle}, {g.row})\n")
            elif g.gate_type=="MEASURE": code.append(f"qc.measure({g.row}, {g.row})\n")

        # second pass: multi-qubit
        bycol={}
        for g in infos:
            bycol.setdefault(g.col,[]).append(g)

        for col, ops in bycol.items():
            ctrls=[g.row for g in ops if g.gate_type=="CTRL"]
            xt=[g.row for g in ops if g.gate_type=="X_T"]
            zt=[g.row for g in ops if g.gate_type=="Z_T"]

            if len(xt)==1:
                t=xt[0]
                if   len(ctrls)==0: code.append(f"qc.x({t})\n")
                elif len(ctrls)==1: code.append(f"qc.cx({ctrls[0]}, {t})\n")
                else: code.append(f"qc.mcx({ctrls}, {t})\n")

            if len(zt)==1:
                t=zt[0]
                if   len(ctrls)==0: code.append(f"qc.z({t})\n")
                elif len(ctrls)==1: code.append(f"qc.cz({ctrls[0]}, {t})\n")
                else: code.append(f"qc.mcz({ctrls}, {t})\n")

        code_str="".join(code)

        dlg=QDialog(self)
        dlg.setWindowTitle("Qiskit Code")
        lay=QVBoxLayout(dlg)
        box=QTextEdit()
        box.setReadOnly(True)
        box.setText(code_str)
        lay.addWidget(box)

        btn=QPushButton("Copy to Clipboard")
        lay.addWidget(btn)
        btn.clicked.connect(lambda: QApplication.clipboard().setText(code_str))
        dlg.resize(600,450)
        dlg.exec()

    # -----------------------------------------------------
    def run_measurement(self):
        try:
            qc=self.build_qiskit_circuit()
        except Exception as e:
            QMessageBox.warning(self,"Error",f"{e}")
            return

        # measurement auto
        has_measure = any(inst.operation.name=="measure" for inst in qc.data)
        if not has_measure:
            qc.measure_all()

        try:
            sim = AerSimulator()
            res = sim.run(qc, shots=1024).result()
            counts = res.get_counts()
        except Exception as e:
            QMessageBox.warning(self,"Simulator Error",f"{e}")
            return

        QMessageBox.information(self,"Measurement Result",str(counts))
    
    # def get_statevector(self):
    #     qc = self.build_qiskit_circuit()
    #     return Statevector.from_instruction(qc)


# ============================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        lay=QVBoxLayout(self)
        tabs=QTabWidget()
        lay.addWidget(tabs)

        tabs.addTab(TutorialTab(),"Tutorial")
        tabs.addTab(ComposerTab(),"Circuit Composer")

        self.setWindowTitle("Quantum Circuit Composer")


def main():
    app=QApplication(sys.argv)
    w=MainWindow()
    w.resize(1350,700) # 창 크기를 튜토리얼 탭에 맞게 조정했습니다.
    w.show()
    sys.exit(app.exec())


if __name__=="__main__":
    main()