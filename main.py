import sys, os, networkx, matplotlib.pyplot, pandas, datetime, pickle
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QLineEdit, QDialog, QMessageBox, QFileDialog, QCheckBox, QMenu, QListWidget, QDateEdit, QSpinBox, QComboBox, QStyle
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch



# event node model
class EventNode:
    def __init__(self, name, date, category=''):
        if category == '':
            category = nocategory()

        self.id = id(self)
        self.name = name
        self.date = date
        self.category = category

    def __getstate__(self):
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date,
            'category': self.category
        }

    def __setstate__(self, state):
        self.id = state['id']
        self.name = state['name']
        self.date = state['date']
        self.category = state['category']



class EventTreeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartEvent")
        self.setWindowIcon(icon())
        self.setMinimumSize(1500, 1500)

        self.end_entry = ""
        self.start_entry = ""
        self.column_width_base = "8.0"
        self.show_timeline = True
        self.graph = networkx.DiGraph()
        self.current_category_filter = []
        self.node_positions = {}
        self.selected_node = None
        self.dragged_node = None
        self.pan_mode = False
        self.current_scale = 1.0
        self.current_time_scale = 1
        self.current_week_offset = 0
        self.project_start = None
        self.project_end = None
        self.week_columns = []
        self.column_width = 2
        self.show_timeline = True
        self.ctrl_pressed = False

        self.current_xlim = (-0.9, 0.9)
        self.current_ylim = (-0.7, 0.7)

        self.setup_ui()
        self.setup_menu()

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
                font-family: "Segoe UI", sans-serif;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QLineEdit, QDateEdit {
                background-color: white;
                border: 1px solid #ccc;
                padding: 5px;
                border-radius: 4px;
            }
            QLabel {
                color: #333;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QDialog {
                background-color: #f0f0f0;
            }
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QCheckBox {
                color: #333;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #0078d4;
            }
            QCheckBox::indicator:unchecked {
                background-color: white;
                border: 1px solid #ccc;
            }
        """)
        
        self.toggle_timeline()
        self.toggle_timeline()

        self.start_up()


# keys
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False

    def on_motion(self, event):
        self.cursorpos_x = event.xdata
        self.cursorpos_y = event.ydata

        if event.button == 1 and self.dragged_node and event.inaxes:
            week = (self.dragged_node.date - self.project_start).days // 7
            column_start = week * self.column_width * self.current_scale
            column_end = (week + 1) * self.column_width * self.current_scale

            new_x = max(column_start, min(event.xdata, column_end))
            new_y = event.ydata
            
            self.node_positions[self.dragged_node] = (new_x, new_y)
            self.update_display()

        elif event.button == 2:
            if not hasattr(self, 'pan_start_x'):
                self.pan_start_x = event.xdata
                self.pan_start_y = event.ydata
                self.initial_xlim = self.ax.get_xlim()
                self.initial_ylim = self.ax.get_ylim()
            else:
                try:
                    dx = (event.xdata - self.pan_start_x)
                    dy = (event.ydata - self.pan_start_y)

                    new_xlim = (self.initial_xlim[0] - dx, self.initial_xlim[1] - dx)
                    new_ylim = (self.initial_ylim[0] - dy, self.initial_ylim[1] - dy)

                    self.current_xlim = new_xlim
                    self.current_ylim = new_ylim
                except:
                    pass

    def on_release(self, event):
        if event.button == 1:
            self.dragged_node = None

        if hasattr(self, 'pan_start_x'):
            del self.pan_start_x
            del self.pan_start_y
            del self.initial_xlim
            del self.initial_ylim

            self.update_display()

    def on_canvas_click(self, event):
        if event.button == 1:
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                min_dist = float('inf')
                closest_node = None

                for node in self.graph.nodes:
                    if node in self.node_positions:
                        nx_pos, ny_pos = self.node_positions[node]
                        dist = (nx_pos - x) ** 2 + (ny_pos - y) ** 2

                        if dist < min_dist:
                            min_dist = dist
                            closest_node = node

                if min_dist < 0.02 and closest_node:
                    self.dragged_node = closest_node
                    self.drag_start_x = x
                    self.drag_start_y = y
                    self.selected_node = closest_node

                    if self.ctrl_pressed:
                        self.highlight_node(closest_node)
                    else:
                        self.update_display()
                else:
                    self.selected_node = None
                    self.update_display()

        elif event.button == 3:
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                min_dist = float('inf')
                closest_node = None

                for node in self.graph.nodes:
                    if node in self.node_positions:
                        nx_pos, ny_pos = self.node_positions[node]
                        dist = (nx_pos - x) ** 2 + (ny_pos - y) ** 2

                        if dist < min_dist:
                            min_dist = dist
                            closest_node = node

                if min_dist < 0.02 and closest_node:
                    self.show_context_menu(closest_node, event)

        elif event.button == 2 and self.ctrl_pressed:
            x, y = event.xdata, event.ydata
            
            x_min = float('inf')
            x_max = 0
            y_min = float('inf')
            y_max = 0
            
            if self.node_positions.values():
                for pos in self.node_positions.values():
                    nx_pos, ny_pos = pos

                    if nx_pos < x_min:
                        x_min = nx_pos
                    elif nx_pos > x_max:
                        x_max = nx_pos

                    if ny_pos < y_min:
                        y_min = ny_pos
                    elif ny_pos > y_max:
                        y_max = ny_pos

                x_center = x_min + ((x_max - x_min) / 2)
                y_center = y_min + ((y_max - y_min) / 2)
                
                self.initial_xlim = self.ax.get_xlim()  
                self.initial_ylim = self.ax.get_ylim()

                new_xlim = (self.initial_xlim[0] - (x - x_center), self.initial_xlim[1] - (x - x_center))
                new_ylim = (self.initial_ylim[0] - (y - y_center), self.initial_ylim[1] - (y - y_center))

                self.current_xlim = new_xlim
                self.current_ylim = new_ylim

                if hasattr(self, 'pan_start_x'):
                    del self.pan_start_x
                    del self.pan_start_y
                    del self.initial_xlim
                    del self.initial_ylim

                self.update_display()

        elif event.button == 2 and not self.ctrl_pressed:
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                min_dist = float('inf')
                closest_node = None
                
                for node in self.graph.nodes:
                    if node in self.node_positions:
                        nx_pos, ny_pos = self.node_positions[node]
                        dist = (nx_pos - x) ** 2 + (ny_pos - y) ** 2

                        if dist < min_dist:
                            min_dist = dist
                            closest_node = node

                if min_dist < 0.02 and closest_node:
                    self.dragged_node = closest_node
                    self.drag_start_x = x
                    self.drag_start_y = y

        elif event.button == 3:
            x, y = event.xdata, event.ydata
            if x is not None and y is not None:
                min_dist = float('inf')
                closest_node = None

                for node in self.graph.nodes:
                    if node in self.node_positions:
                        nx_pos, ny_pos = self.node_positions[node]
                        dist = (nx_pos - x) ** 2 + (ny_pos - y) ** 2

                        if dist < min_dist:
                            min_dist = dist
                            closest_node = node

                if min_dist < 0.02 and closest_node:
                    self.show_context_menu(closest_node, event)

    def highlight_node(self, node):
        self.ax.clear()
        filtered_nodes = self.get_filtered_nodes()
        subgraph = self.graph.subgraph(filtered_nodes)
        pos = {n: self.node_positions[n] for n in subgraph.nodes if n in self.node_positions}

        networkx.draw(subgraph, pos, ax=self.ax,
                labels={n: f"{n.name}\n{n.date.strftime('%d.%m.%Y')}\n({n.category})" for n in subgraph.nodes},
                node_size=2500 * self.current_scale,
                node_color='lightblue',
                edge_color='gray',
                font_size=9 * self.current_scale,
                arrows=True,
                arrowstyle='-|>',
                arrowsize=20 * self.current_scale)

        if node:
            networkx.draw_networkx_nodes(subgraph, pos, nodelist=[node], node_color='salmon', ax=self.ax)
            networkx.draw_networkx_edges(subgraph, pos, edgelist=self.graph.edges(node), edge_color='red', ax=self.ax)

        self.canvas.draw()

    def wheelEvent(self, event):
        if self.ctrl_pressed:
            delta = event.angleDelta().y() / 120
            scale_factor = 1.1

            if delta > 0:
                self.current_scale *= scale_factor
            else:
                self.current_scale /= scale_factor

            # self.current_scale = max(0.1, min(self.current_scale, 10.0))

            for node in self.node_positions:
                x, y = self.node_positions[node]
                new_x = x * (scale_factor if delta > 0 else 1 / scale_factor)
                # new_y = y * (scale_factor if delta > 0 else 1 / scale_factor)
                new_y = y
                self.node_positions[node] = (new_x, new_y)

            if self.cursorpos_x and self.cursorpos_y:
                self.initial_xlim = self.ax.get_xlim()  
                self.initial_ylim = self.ax.get_ylim()
                
                dx = self.cursorpos_x - (self.cursorpos_x * (scale_factor if delta > 0 else 1 / scale_factor)) 
                dy = self.cursorpos_y - (self.cursorpos_y * (scale_factor if delta > 0 else 1 / scale_factor)) 
                new_xlim = (self.initial_xlim[0] - dx, self.initial_xlim[1] - dx)
                # new_ylim = (self.initial_ylim[0] - dy, self.initial_ylim[1] - dy)
                new_ylim = (self.initial_ylim[0], self.initial_ylim[1])

                self.current_xlim = new_xlim
                self.current_ylim = new_ylim

                if hasattr(self, 'pan_start_x'):
                    del self.pan_start_x
                    del self.pan_start_y
                    del self.initial_xlim
                    del self.initial_ylim

            self.update_display()


# context menu
    def show_context_menu(self, node, event):
        menu = QMenu(self)
        show_previous_action = menu.addAction("Показать все предыдущие")
        show_next_action = menu.addAction("Показать все последующие")

        action = menu.exec_(self.mapToGlobal(QPoint(int(event.x), int(event.y))))

        if action == show_previous_action:
            self.show_previous_events(node)
        elif action == show_next_action:
            self.show_next_events(node)

    def show_previous_events(self, node):
        previous_nodes = set()
        self.collect_previous_nodes(node, previous_nodes)
        self.current_category_filter = list(previous_nodes)
        self.update_display()

    def collect_previous_nodes(self, node, previous_nodes):
        for predecessor in self.graph.predecessors(node):
            previous_nodes.add(predecessor)
            self.collect_previous_nodes(predecessor, previous_nodes)

    def show_next_events(self, node):
        next_nodes = set()
        self.collect_next_nodes(node, next_nodes)
        self.current_category_filter = list(next_nodes)
        self.update_display()

    def collect_next_nodes(self, node, next_nodes):
        for successor in self.graph.successors(node):
            next_nodes.add(successor)
            self.collect_next_nodes(successor, next_nodes)


# render
    def update_display(self):
        self.ax.clear()
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        self.ax.set_xlim(self.current_xlim)
        self.ax.set_ylim(self.current_ylim)

        self.update_event_positions()

        if self.week_columns and self.show_timeline:
            start_week = self.current_week_offset
            end_week = start_week + self.current_time_scale

            for i in range(start_week, end_week):
                if i >= len(self.week_columns):
                    break

                start_of_week, end_of_week = self.week_columns[i]
                x = (i - start_week) * self.column_width * self.current_scale

                if self.current_xlim[0] <= x <= self.current_xlim[1]:
                    self.ax.text(x, self.current_ylim[1], f"{start_of_week.strftime('%d\n%m')}", ha='center', va='bottom', fontsize=8 * self.current_scale, color='black')
                    self.ax.axvline(x,color='gray', linestyle='--', alpha=0.5, linewidth=0.3)

        filtered_nodes = self.get_filtered_nodes()
        subgraph = self.graph.subgraph(filtered_nodes)

        if subgraph.nodes:
            for node in subgraph.nodes:
                if node in self.node_positions:
                    x, y = self.node_positions[node]
                    color = 'salmon' if node == self.selected_node else '#b9d0f0'

                    if self.current_xlim[0] <= x <= self.current_xlim[1] and self.current_ylim[0] <= y <= self.current_ylim[1]:
                        text = f"{node.name}\n{node.date.strftime('%d.%m.%Y')}\n({node.category})"
                        fontsize = 8 * self.current_scale
                        text_obj = self.ax.text(x, y, text, ha='center', va='center', fontsize=fontsize, color='black')

                        bbox = text_obj.get_window_extent(renderer=self.figure.canvas.get_renderer())
                        bbox = bbox.transformed(self.ax.transData.inverted())

                        width = bbox.width * 1
                        height = bbox.height * 1

                        rect = FancyBboxPatch((x - width / 2, y - height / 2), width, height, boxstyle="round,pad=0.01", edgecolor='black', facecolor=color, alpha=0.8, lw=1)
                        self.ax.add_patch(rect)

            for u, v in subgraph.edges:
                if u not in self.node_positions or v not in self.node_positions:
                    continue

                x1, y1 = self.node_positions[u]
                x2, y2 = self.node_positions[v]
                mid_x = ((x1 + x2) / 2)
                mid_y = ((y1 + y2) / 2)

                if (self.current_xlim[0] <= x1 <= self.current_xlim[1] and self.current_ylim[0] <= y1 <= self.current_ylim[1]) or (self.current_xlim[0] <= x2 <= self.current_xlim[1] and self.current_ylim[0] <= y2 <= self.current_ylim[1]):
                    x_offset = width/(1.5*(self.current_scale**(0.25)))
                    x1 = x1 + x_offset
                    x2 = x2 - x_offset
                    x_offset = 0.02

                    if x1+x_offset>=x2-x_offset:
                        self.ax.arrow(x1, y1, x_offset, 0, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0, head_length=0)
                        self.ax.arrow(x1+x_offset, y1, 0, mid_y-y1, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0, head_length=0)
                        self.ax.arrow(x1+x_offset, mid_y, x2-x1-2*x_offset, 0, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0, head_length=0)
                        self.ax.arrow(x2-x_offset, mid_y, 0, y2-mid_y, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0, head_length=0)
                        self.ax.arrow(x2-x_offset, y2, x_offset, 0, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0.01, head_length=0.01, length_includes_head = True)
                    else:
                        self.ax.arrow(x1, y1, mid_x-x1, 0, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0, head_length=0)
                        self.ax.arrow(mid_x, y1, 0, y2-y1, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0, head_length=0)
                        self.ax.arrow(mid_x, y2, x2-mid_x, 0, color='gray', linestyle='-', width=0.001 * self.current_scale, head_width=0.01, head_length=0.01, length_includes_head = True)

        if self.week_columns and self.show_timeline and not subgraph.nodes:
            start_week = self.current_week_offset
            end_week = start_week + self.current_time_scale

            for i in range(start_week, end_week):
                if i >= len(self.week_columns):
                    break

                start_of_week, end_of_week = self.week_columns[i]
                x = (i - start_week + 0.5) * self.column_width * self.current_scale
                
                if self.current_xlim[0] <= x <= self.current_xlim[1]:
                    self.ax.text(x, 1.05, f"{start_of_week.strftime('%d\n%m')}", ha='center', va='bottom', fontsize=8 * self.current_scale, color='black')
                    self.ax.axvline((i - start_week) * self.column_width * self.current_scale, color='gray', linestyle='--', alpha=0.3, linewidth=1 * self.current_scale)

        self.canvas.draw()
        
    def update_event_positions(self):
        for node in self.graph.nodes:
            week = (node.date - self.project_start).days // 7
            week = week - self.current_week_offset

            if week != -1:
                column_start = week * self.column_width * self.current_scale
                column_end = (week + 1) * self.column_width * self.current_scale

                new_y = self.node_positions[node][1]
                new_x = self.node_positions[node][0]
                new_x = min(new_x, column_end)
                new_x = max(column_start, new_x)
                
                self.node_positions[node] = (new_x, new_y)

    def set_dates(self):
            self.project_start = datetime.datetime.strptime(self.start_entry, "%d.%m.%Y").date()
            self.project_end = datetime.datetime.strptime(self.end_entry, "%d.%m.%Y").date()

            self.calculate_calendar_weeks()
            self.current_time_scale = len(self.week_columns)
            self.column_width = float(self.column_width_base) / self.current_time_scale

            self.update_display()

    def calculate_calendar_weeks(self):
        self.week_columns = []
        current_date = self.project_start

        while current_date <= self.project_end:
            start_of_week = current_date - datetime.timedelta(days=current_date.weekday())
            end_of_week = start_of_week + datetime.timedelta(days=6)

            if end_of_week > self.project_end:
                end_of_week = self.project_end

            self.week_columns.append((start_of_week, end_of_week))
            current_date = end_of_week + datetime.timedelta(days=1)

    def calculate_week_position(self, date):
        for i, (start_of_week, end_of_week) in enumerate(self.week_columns):
            if start_of_week <= date <= end_of_week:
                days_in_week = (end_of_week - start_of_week).days + 1
                day_in_week = (date - start_of_week).days
                x = (i + (day_in_week / days_in_week)) * self.column_width
                return x
        return 0.5


# startup dialog
    def start_up(self):
        dialog = QDialog(self)
        dialog.rejected.connect(sys.exit)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("SmartEvent")
        layout = QVBoxLayout(dialog)

        button_new = QPushButton("Новый проект")
        button_new.clicked.connect(self.start_up_new_project)
        layout.addWidget(button_new)

        button_open = QPushButton("Открыть проект")
        button_open.clicked.connect(self.start_up_open_project)
        layout.addWidget(button_open)

        dialog.exec_()

    def start_up_new_project(self):
        self.sender().parent().accept()
        self.new_project()

    def start_up_open_project(self):
        self.sender().parent().accept()
        self.open_project()


# menu
    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('Меню')
        file_menu.addAction('Изменить даты проекта', self.edit_project_dates)
        file_menu.addSeparator()
        file_menu.addAction('Новый проект', self.new_project)
        file_menu.addAction('Открыть...', self.open_project)
        file_menu.addAction('Сохранить как...', self.save_project)
        file_menu.addSeparator()
        file_menu.addAction('Выход', self.close)
    
    def new_project(self):
        self.graph = networkx.DiGraph()
        self.node_positions = {}
        self.current_category_filter = []
        self.selected_node = None
        self.project_start = None
        self.project_end = None
        self.week_columns = []
        self.column_width = 0
        self.update_display()
        self.edit_project_dates()

    def open_project(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", "Файлы проектов (*.pkl)")
        if filepath:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            self.graph = data['graph']
            self.node_positions = data.get('positions', {})
            self.current_category_filter = data.get('filter', [])
            self.start_entry = data.get('project_start').strftime("%d.%m.%Y")
            self.end_entry = data.get('project_end').strftime("%d.%m.%Y")
            self.current_scale = data.get('current_scale', 1.0)
            self.current_week_offset = data.get('current_week_offset', 0)
            self.current_xlim = data.get('current_xlim', (-0.9, 0.9))
            self.current_ylim = data.get('current_ylim', (-0.7, 0.7))
            self.column_width_base = data.get('column_width_base', "8.0")

            self.set_dates()

    def save_project(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить проект", "", "Файлы проектов (*.pkl)")
        if filepath:
            data = {
                'graph': self.graph,
                'positions': self.node_positions,
                'filter': self.current_category_filter,
                'project_start': self.project_start,
                'project_end': self.project_end,
                'current_scale': self.current_scale,
                'current_week_offset': self.current_week_offset,
                'current_xlim': self.current_xlim,
                'current_ylim': self.current_ylim,
                'column_width_base': self.column_width_base,
            }
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            QMessageBox.information(self, "Успех", "Проект успешно сохранен")

    def edit_project_dates(self):
        dialog = QDialog(self)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("Даты проекта")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Дата начала (ДД.ММ.ГГГГ):"))
        self.start_entry = QLineEdit(self.start_entry)
        layout.addWidget(self.start_entry)

        layout.addWidget(QLabel("Дата окончания (ДД.ММ.ГГГГ):"))
        self.end_entry = QLineEdit(self.end_entry)
        layout.addWidget(self.end_entry)

        layout.addWidget(QLabel("Ширина недели:"))
        self.column_width_base = QLineEdit(self.column_width_base)
        layout.addWidget(self.column_width_base)

        button = QPushButton("Установить")
        button.clicked.connect(self.edit_project_dates_set_dates)
        layout.addWidget(button)

        dialog.exec_()

    def edit_project_dates_set_dates(self):
        try:
            self.start_entry = self.start_entry.text()
            self.end_entry = self.end_entry.text()
            self.column_width_base = self.column_width_base.text()
            self.project_start = datetime.datetime.strptime(self.start_entry, "%d.%m.%Y").date()
            self.project_end = datetime.datetime.strptime(self.end_entry, "%d.%m.%Y").date()

            if self.project_start >= self.project_end:
                raise ValueError("Дата окончания должна быть позже даты начала")
            
            self.set_dates()

            self.sender().parent().accept()
            return True

        except ValueError as e:
            QMessageBox.critical(self, "Ошибка", f"Некорректный ввод: {str(e)}")
            return False


# buttons
    def setup_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        self.main_layout = QHBoxLayout(self.main_widget)
        self.figure = matplotlib.pyplot.figure(figsize=(16, 10), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#ffffff')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect('button_press_event', self.on_canvas_click)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.main_layout.addWidget(self.canvas, 1)

        self.control_frame = QWidget()
        self.control_layout = QVBoxLayout(self.control_frame)
        self.control_layout.setAlignment(Qt.AlignTop)
        self.control_frame.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        self.main_layout.addWidget(self.control_frame)

        buttons = [
            ("Показать шкалу времени", self.toggle_timeline),
            ("Добавить событие", self.add_event),
            ("Добавить предыдущее", lambda: self.add_related_event('previous')),
            ("Добавить следующее", lambda: self.add_related_event('next')),
            ("Редактировать событие", self.edit_event_properties),
            ("Удалить событие", self.delete_event),
            ("Связать события", self.link_events),
            ("Фильтр по категориям", self.filter_by_category),
            ("Экспорт в Excel", self.export_to_excel),
            ("Экспорт в изображение", self.export_to_image),
            ("Экспорт в PDF", self.export_to_pdf)
        ]

        for text, cmd in buttons:
            button = QPushButton(text)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #006cbd;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
            """)
            button.clicked.connect(cmd)
            self.control_layout.addWidget(button)

    def toggle_timeline(self):
        self.show_timeline = not self.show_timeline
        self.update_display()

    def add_event(self, parent=None):
        dialog = QDialog(self)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("Новое событие")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Название:"))
        name_entry = QLineEdit()
        layout.addWidget(name_entry)

        layout.addWidget(QLabel("Дата (ДД.ММ.ГГГГ):"))
        date_entry = QDateEdit(calendarPopup=True)
        date_entry.setDate(datetime.date.today())
        date_entry.setDisplayFormat("dd.MM.yyyy")
        layout.addWidget(date_entry)

        layout.addWidget(QLabel("Категория:"))
        category_entry = QLineEdit()
        layout.addWidget(category_entry)

        button = QPushButton("Создать")
        button.clicked.connect(lambda: self.add_event_click(name_entry, date_entry, category_entry, dialog, parent))
        layout.addWidget(button)

        dialog.exec_()

    def add_event_click(self, name_entry, date_entry, category_entry, dialog, parent):
        try:
            name = name_entry.text()
            if not name:
                raise ValueError("Название события не может быть пустым")

            date = date_entry.date().toPyDate()

            if date < self.project_start or date > self.project_end:
                raise ValueError("Дата должна быть в рамках проекта")

            category = category_entry.text() or nocategory()

            new_event = EventNode(name, date, category)
            self.graph.add_node(new_event)

            x = self.calculate_week_position(date)
            y = 0.1 + 0.8 * len(self.graph.nodes) / (len(self.graph.nodes) + 1)
            y = max(0.1, min(y, 0.9))
            week_index = -1

            for i, (start_of_week, end_of_week) in enumerate(self.week_columns):
                if start_of_week <= date <= end_of_week:
                    week_index = i
                    break

            if week_index != -1:
                column_start = week_index * self.column_width
                column_end = (week_index + 1) * self.column_width
                x = max(column_start, min(x, column_end))

            self.node_positions[new_event] = (x, y)

            if parent:
                self.graph.add_edge(parent, new_event)

            self.update_display()
            dialog.close()

        except ValueError as e:
            QMessageBox.critical(self, "Ошибка", f"Некорректный ввод: {str(e)}")

    def add_related_event(self, relation_type):
        selected = self.selected_node
        if not selected:
            QMessageBox.warning(self, "Внимание", "Сначала выберите событие!")
            return

        dialog = QDialog(self)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("Добавить связанное событие")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Название:"))
        name_entry = QLineEdit()
        layout.addWidget(name_entry)

        layout.addWidget(QLabel("Выберите способ задания даты:"))
        date_type = QComboBox()
        date_type.addItem("Календарь")
        date_type.addItem("Длительность")
        layout.addWidget(date_type)

        date_entry = QDateEdit(calendarPopup=True)
        date_entry.setDate(datetime.date.today())
        date_entry.setDisplayFormat("dd.MM.yyyy")
        layout.addWidget(date_entry)

        duration_entry = QSpinBox()
        duration_entry.setRange(1, 365)
        duration_entry.setValue(1)
        duration_entry.setSuffix(" дней")
        duration_entry.hide()
        layout.addWidget(duration_entry)

        def toggle_date_widget(index):
            if index == 0:
                date_entry.show()
                duration_entry.hide()
            else:
                date_entry.hide()
                duration_entry.show()

        date_type.currentIndexChanged.connect(toggle_date_widget)

        layout.addWidget(QLabel("Категория:"))
        category_entry = QLineEdit()
        layout.addWidget(category_entry)

        button = QPushButton("Создать")
        button.clicked.connect(lambda: self.add_related_event_click(name_entry, date_entry, duration_entry, date_type, category_entry, dialog, selected, relation_type))
        layout.addWidget(button)

        dialog.exec_()

    def add_related_event_click(self, name_entry, date_entry, duration_entry, date_type, category_entry, dialog, selected, relation_type):
        try:
            name = name_entry.text()

            if not name:
                raise ValueError("Название события не может быть пустым")
            
            if date_type.currentIndex() == 0:
                date = date_entry.date().toPyDate()
            else:
                duration = duration_entry.value()

                if relation_type == 'previous':
                    date = selected.date - datetime.timedelta(days=duration)
                else:
                    date = selected.date + datetime.timedelta(days=duration)

            if date < self.project_start or date > self.project_end:
                raise ValueError("Дата должна быть в рамках проекта")

            category = category_entry.text() or nocategory()

            new_event = EventNode(name, date, category)
            self.graph.add_node(new_event)

            x = self.calculate_week_position(date)

            if selected in self.node_positions:
                parent_x, parent_y = self.node_positions[selected]
                self.node_positions[new_event] = (x, parent_y)
            else:
                self.node_positions[new_event] = (x, 0.5)

            if relation_type == 'previous':
                self.graph.add_edge(new_event, selected)
            elif relation_type == 'next':
                self.graph.add_edge(selected, new_event)

            self.update_display()
            dialog.close()
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка", f"Некорректный ввод: {str(e)}")

    def edit_event_properties(self):
        selected = self.selected_node
        if not selected:
            QMessageBox.warning(self, "Внимание", "Сначала выберите событие!")
            return

        dialog = QDialog(self)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("Редактирование события")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Название:"))
        name_entry = QLineEdit(selected.name)
        layout.addWidget(name_entry)

        layout.addWidget(QLabel("Дата (ДД.ММ.ГГГГ):"))
        date_entry = QDateEdit(calendarPopup=True)
        date_entry.setDate(selected.date)
        date_entry.setDisplayFormat("dd.MM.yyyy")
        layout.addWidget(date_entry)

        layout.addWidget(QLabel("Категория:"))
        category_entry = QLineEdit(selected.category)
        layout.addWidget(category_entry)

        button = QPushButton("Сохранить")
        button.clicked.connect(lambda: self.edit_event_properties_click(name_entry, date_entry, category_entry, dialog, selected))
        layout.addWidget(button)

        dialog.exec_()

    def edit_event_properties_click(self, name_entry, date_entry, category_entry, dialog, selected):
        try:
            selected.name = name_entry.text()
            selected.date = date_entry.date().toPyDate()

            if selected.date < self.project_start or selected.date > self.project_end:
                raise ValueError("Дата должна быть в рамках проекта")

            selected.category = category_entry.text()
            x = self.calculate_week_position(selected.date)
            current_y = self.node_positions[selected][1]
            week_index = -1

            for i, (start_of_week, end_of_week) in enumerate(self.week_columns):
                if start_of_week <= selected.date <= end_of_week:
                    week_index = i
                    break

            if week_index != -1:
                column_start = week_index * self.column_width
                column_end = (week_index + 1) * self.column_width
                x = max(column_start, min(x, column_end))

            self.node_positions[selected] = (x, current_y)

            self.update_display()
            dialog.close()

        except ValueError as e:
            QMessageBox.critical(self, "Ошибка", f"Некорректный ввод: {str(e)}")

    def delete_event(self):
        selected = self.selected_node
        if selected:
            self.graph.remove_node(selected)
            if selected in self.node_positions:
                del self.node_positions[selected]
            self.selected_node = None
            self.update_display()

    def link_events(self):
        if not self.selected_node:
            QMessageBox.warning(self, "Внимание", "Сначала выберите событие!")
            return

        dialog = QDialog(self)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("Связать события")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Выберите событие для связи:"))
        event_list = QListWidget()
        for node in self.graph.nodes:
            if node != self.selected_node:
                event_list.addItem(f"{node.name} ({node.date.strftime('%d.%m.%Y')})")
        layout.addWidget(event_list)

        button = QPushButton("Связать")
        button.clicked.connect(lambda: self.link_events_click(event_list, dialog))
        layout.addWidget(button)

        dialog.exec_()

    def link_events_click(self, event_list, dialog):
        selected_item = event_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Внимание", "Сначала выберите событие!")
            return

        selected_event_name = selected_item.text().split(" (")[0]
        selected_event = next((n for n in self.graph.nodes if n.name == selected_event_name), None)

        if selected_event:
            self.graph.add_edge(self.selected_node, selected_event)
            self.update_display()
            dialog.close()
        else:
            QMessageBox.warning(self, "Ошибка", "Событие не найдено!")

    def filter_by_category(self):
        categories = list(set(n.category for n in self.graph.nodes))
        dialog = QDialog(self)
        dialog.setMinimumSize(500,300)
        dialog.setWindowTitle("Фильтр по категориям")
        layout = QVBoxLayout(dialog)

        selected_vars = {cat: QCheckBox(cat) for cat in categories}
        for cat, checkbox in selected_vars.items():
            checkbox.setChecked(cat in self.current_category_filter)
            layout.addWidget(checkbox)

        button = QPushButton("Применить")
        button.clicked.connect(lambda: self.filter_by_category_click(selected_vars, dialog))
        layout.addWidget(button)

        dialog.exec_()

    def filter_by_category_click(self, selected_vars, dialog):
        self.current_category_filter = [cat for cat, checkbox in selected_vars.items() if checkbox.isChecked()]
        dialog.close()
        self.update_display()

    def export_to_excel(self):
        if not self.graph.nodes:
            QMessageBox.warning(self, "Внимание", "Нет событий для экспорта!")
            return

        df = pandas.DataFrame([(n.name, n.date.strftime("%d.%m.%Y"), n.category) for n in self.get_filtered_nodes()], columns=["Событие", "Дата", "Категория"])

        filename, _ = QFileDialog.getSaveFileName(self, "Экспорт в Excel", "", "Excel файлы (*.xlsx)")
        if filename:
            df.to_excel(filename, index=False)
            QMessageBox.information(self, "Успех", f"Данные экспортированы в {filename}")

    def export_to_image(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Экспорт в изображение", "", "PNG файлы (*.png)")
        if filename:
            self.figure.savefig(filename, bbox_inches='tight', dpi=150)
            QMessageBox.information(self, "Успех", f"Изображение сохранено в {filename}")

    def export_to_pdf(self):
        if not self.graph.nodes:
            QMessageBox.warning(self, "Внимание", "Нет событий для экспорта!")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Экспорт в PDF", "", "PDF файлы (*.pdf)")
        if filename:
            with PdfPages(filename) as pdf:
                self.figure.savefig(pdf, format='pdf', bbox_inches='tight')
            QMessageBox.information(self, "Успех", f"PDF документ сохранен в {filename}")


# help methods
    def get_filtered_nodes(self):
        return [n for n in self.graph.nodes if
                not self.current_category_filter or n.category in self.current_category_filter]

    def get_selected_event(self):
        if not self.selected_node:
            QMessageBox.warning(self, "Внимание", "Сначала выберите событие!")
            return None
        return next((n for n in self.graph.nodes if n.id == self.selected_node), None)

    def closeEvent(self, event):
        if self.graph.nodes:
            reply = QMessageBox.question(self, 'Сохранить проект', 'Хотите сохранить проект перед закрытием?', QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                self.save_project()
                event.accept()
            elif reply == QMessageBox.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()



# global help methods
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def icon():
    return QIcon(resource_path("icon.ico"))

def nocategory():
    return "Без категории"



# entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EventTreeApp()
    window.show()
    app.setWindowIcon(icon())
    sys.exit(app.exec_())