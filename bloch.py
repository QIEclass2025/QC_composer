from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

# [수정] PyQt6 Imports: ScrollArea, SizePolicy 추가됨
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QLabel, QTabWidget, QDialog, QTextEdit,
    QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QBrush
from PyQt6.QtCore import Qt, QRectF

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

# [추가] 시각화 및 계산을 위한 필수 라이브러리 (기존 코드엔 없던 부분)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from qiskit.visualization import plot_bloch_multivector
from qiskit.quantum_info import Statevector, partial_trace, Operator
import numpy as np


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
# [신규 추가] Bloch Sphere Visualization Canvas
# (얽힘 상태일 때 강제로 화살표를 보여주는 로직이 포함됨)
# ============================================
class BlochCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(10, 10, 10, 10)
        
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_box.addWidget(self.title_label)

        self.status_label = QLabel()
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_box.addWidget(self.status_label)
        
        self.current_canvas = None
        # 화면 잘림 방지를 위한 최소 높이 설정
        self.setMinimumHeight(550) 
        self.hide() 

    def update_bloch(self, density_matrix, qubit_index):
        if self.current_canvas is not None:
            self.layout_box.removeWidget(self.current_canvas)
            self.current_canvas.setParent(None)
            self.current_canvas = None

        # --- [핵심] 얽힘 상태 강제 보정 로직 ---
        # 1. 현재 상태의 벡터 길이 계산
        X = Operator.from_label('X')
        Y = Operator.from_label('Y')
        Z = Operator.from_label('Z')
        
        vx = np.real(density_matrix.expectation_value(X))
        vy = np.real(density_matrix.expectation_value(Y))
        vz = np.real(density_matrix.expectation_value(Z))
        
        vector_length = np.sqrt(vx**2 + vy**2 + vz**2)
        
        final_rho = density_matrix
        is_forced = False
        
        # 2. 벡터 길이가 1보다 작으면(얽힘 상태) 강제로 늘림
        if vector_length < 0.99:
            is_forced = True
            if vector_length < 0.01:
                # 길이가 0인 경우 (예: 벨 상태) -> X축 방향 (|+>) 으로 강제 설정
                nx, ny, nz = 1.0, 0.0, 0.0
            else:
                # 방향은 유지하되 길이만 1로 정규화
                nx, ny, nz = vx / vector_length, vy / vector_length, vz / vector_length
            
            # 정규화된 벡터로 밀도 행렬 재구성
            I = Operator.from_label('I')
            final_rho = 0.5 * (I + nx * X + ny * Y + nz * Z)
        # --------------------------------

        # 3. 그래프 그리기
        new_fig = plot_bloch_multivector(final_rho) 
        new_fig.set_size_inches(5, 5)
        new_fig.tight_layout(pad=3.0)
        plt.close(new_fig)

        self.current_canvas = FigureCanvasQTAgg(new_fig)
        self.current_canvas.setMinimumSize(450, 450)
        self.current_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.title_label.setText(f"Bloch Sphere: Qubit {qubit_index}")
        
        if is_forced:
            self.status_label.setText("★ Forced Pure State (강제 보정됨)\n얽힘 상태를 순수 상태로 변환하여 표시 중")
            self.status_label.setStyleSheet("color: blue; font-weight: bold;")
        else:
            self.status_label.setText("Pure State (Length = 1.0)")
            self.status_label.setStyleSheet("color: green;")

        self.layout_box.addWidget(self.current_canvas)
        self.show()


# ============================================
# [신규 추가] 와이어 끝에 달릴 버튼 아이템
# ============================================
class BlochButtonItem(QGraphicsRectItem):
    WIDTH = 45
    HEIGHT = 25
    def __init__(self, qubit_index, callback, x, y):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.qubit_index = qubit_index
        self.callback = callback
        self.setPos(x, y)
        self.setBrush(QBrush(QColor("#FF9933"))) 
        self.setPen(QPen(Qt.GlobalColor.black))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptHoverEvents(True)

        self.text = QGraphicsTextItem("Bloch", self)
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        self.text.setFont(font)
        r = self.rect()
        b = self.text.boundingRect()
        self.text.setPos((r.width() - b.width()) / 2, (r.height() - b.height()) / 2)

    def mousePressEvent(self, event):
        if self.callback: self.callback(self.qubit_index)


# ============================================
# Gate item UI (원본 유지)
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
# Circuit View (일부 수정: 버튼 그리기 추가)
# ============================================
class CircuitView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.WIRE_SHIFT = -30
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # 세로 스크롤은 메인 윈도우에 맡김

        self.n_qubits = N_QUBITS
        self.circuit: Dict[Tuple[int, int], GateItem] = {}
        self.palette_gate: Optional[GateItem] = None
        self.connection_lines: List = []
        
        # [추가] 콜백 함수 저장 변수
        self.bloch_callback = None

        self._update_scene_rect()
        self._draw_all()

    # [추가] 콜백 설정 메서드
    def set_bloch_callback(self, func):
        self.bloch_callback = func
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
        # 뷰 자체의 높이 확보
        self.setMinimumHeight(int(height) + 50)

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

            # [추가] 와이어 끝에 Bloch 버튼 그리기
            if self.bloch_callback:
                bx = right + self.WIRE_SHIFT + 10
                by = y - BlochButtonItem.HEIGHT/2
                btn = BlochButtonItem(i, self.bloch_callback, bx, by)
                self.scene.addItem(btn)

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
# Tutorial Tab (dummy)
# ============================================
class TutorialTab(QWidget):
    def __init__(self):
        super().__init__()
        lay=QVBoxLayout(self)
        t=QLabel("Quantum Algorithm Tutorial (준비중)")
        t.setFont(QFont("Segoe UI",12))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)


# ============================================
# Composer Tab (구조 수정: 상단 회로 / 하단 블로흐 구)
# ============================================
class ComposerTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # [수정] 메인 레이아웃을 VBox로 변경 (위: 회로 / 아래: 캔버스)
        layout_root = QVBoxLayout(self)

        # 1. 상단 회로 영역 위젯 생성
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # 기존 코드의 Panel & View 연결
        panel = QVBoxLayout()
        top_layout.addLayout(panel)

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
        top_layout.addWidget(self.view, stretch=1)

        # [추가] 뷰에 콜백 연결
        self.view.set_bloch_callback(self.update_single_bloch)

        # 상단 영역을 루트 레이아웃에 추가
        layout_root.addWidget(top_widget)

        # 2. 하단 블로흐 캔버스 추가
        layout_root.addSpacing(15)
        self.bloch_canvas = BlochCanvas(self)
        layout_root.addWidget(self.bloch_canvas)

        # 기존 버튼 연결 유지
        btn_add.clicked.connect(self.add_q)
        btn_del.clicked.connect(self.del_q)
        self.btn_export.clicked.connect(self.export_qiskit)
        self.btn_measure.clicked.connect(self.run_measurement)

    # [추가] 블로흐 구 업데이트 함수
    def update_single_bloch(self, target_qubit_idx):
        try:
            # 회로 빌드
            qc = self.build_qiskit_circuit()
            # 상태 벡터 계산
            full_state = Statevector.from_instruction(qc)
            
            # 관심 없는 큐빗 날리기 (Partial Trace)
            all_qubits = list(range(self.view.n_qubits))
            trace_out_qubits = [q for q in all_qubits if q != target_qubit_idx]
            
            rho = partial_trace(full_state, trace_out_qubits)
            
            # 캔버스 업데이트 (여기서 강제 보정 로직이 수행됨)
            self.bloch_canvas.update_bloch(rho, target_qubit_idx)

        except Exception as e:
            QMessageBox.warning(self, "Bloch Error", f"Calculation Failed: {e}")
            self.bloch_canvas.hide()

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
    # Export QISKIT CODE
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


# ============================================
# Main Window (수정: ScrollArea 적용)
# ============================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quantum Circuit Composer")
        self.resize(1350, 900) # 창 크기 넉넉하게

        # [수정] 전체 스크롤 영역 생성
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True) 

        # 탭 위젯 생성
        self.tabs = QTabWidget()
        self.tabs.addTab(TutorialTab(), "Tutorial")
        self.tabs.addTab(ComposerTab(), "Circuit Composer")

        # 스크롤 영역에 탭 설정
        scroll_area.setWidget(self.tabs)

        # 메인 레이아웃에 스크롤 영역 추가
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)


def main():
    app=QApplication(sys.argv)
    w=MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__=="__main__":
    main()