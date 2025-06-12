import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton, QAction, QLineEdit, QHBoxLayout, QFileDialog, QWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.uic import loadUi
import logging
import os
import warnings
from datetime import datetime
import csv

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Try importing MapDialog
try:
    from map_dialog import MapDialog
    logger.debug("Successfully imported MapDialog")
except ImportError as e:
    logger.error(f"Failed to import MapDialog: {str(e)}")
    QMessageBox.critical(None, "Error", f"Failed to import MapDialog: {str(e)}\nEnsure 'map_dialog.py' is in the correct directory and 'folium' is installed.")
    sys.exit(1)

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

class LockerDetailDialog(QDialog):
    def __init__(self, locker_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Details for {locker_data['lockerId']}")
        self.locker_data = locker_data
        layout = QVBoxLayout()
        self.fields = {}
        for key, value in locker_data.items():
            if key not in ["_id", "createdAt", "updatedAt"]:
                label = QLabel(f"{key.replace('_', ' ').title()}:")
                input_field = QLineEdit(str(value) if value is not None else "")
                self.fields[key] = input_field
                layout.addWidget(label)
                layout.addWidget(input_field)
        
        # Edit button
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(self.edit_locker)
        layout.addWidget(edit_button)

        self.setLayout(layout)
        self.setMinimumSize(400, 350)

    def edit_locker(self):
        try:
            data = {
                "lockerId": self.locker_data["lockerId"],
                "status": self.fields["status"].text() if self.fields["status"].text() else self.locker_data["status"],
                "lightStatus": self.fields["lightStatus"].text() if self.fields["lightStatus"].text() else self.locker_data["lightStatus"],
                "batteryPercentage": float(self.fields["batteryPercentage"].text()) if self.fields["batteryPercentage"].text() else self.locker_data["batteryPercentage"],
                "latitude": float(self.fields["latitude"].text()) if self.fields["latitude"].text() else self.locker_data["latitude"],
                "longitude": float(self.fields["longitude"].text()) if self.fields["longitude"].text() else self.locker_data["longitude"]
            }
            response = requests.put(f"https://locker-api.vercel.app/locker/update/{self.locker_data['lockerId']}", json=data)
            response.raise_for_status()
            result = response.json()
            if result["success"]:
                QMessageBox.information(self, "Success", "Locker updated successfully")
                self.accept()
            else:
                raise Exception(result["message"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update locker: {str(e)}")

class LockerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing LockerApp")
        self.table_lockers_data = []
        self.selected_locker_id = None

        # Load UI file
        ui_file = "locker.ui"
        current_dir = os.getcwd()
        ui_path = os.path.join(current_dir, ui_file)
        logger.debug(f"Looking for UI file at: {ui_path}")
        if not os.path.exists(ui_path):
            logger.error(f"UI file '{ui_file}' not found at {ui_path}")
            QMessageBox.critical(None, "Error", f"UI file '{ui_file}' not found")
            sys.exit(1)
        try:
            with open(ui_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logger.debug(f"Total lines in UI file: {len(lines)}")
                logger.debug(f"First 100 chars: {''.join(lines)[:100]}...")
            loadUi(ui_file, self)
        except Exception as e:
            logger.error(f"Failed to load UI file: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to load UI file: {str(e)}\nCheck 'locker.ui' for XML syntax errors.")
            sys.exit(1)
        self.setWindowTitle("Locker Management System")

        self.resize(1000, 600) 

        # Setup Status Bar
        self.student_name = "I Nengah Dwi Putra Witarsana"
        self.student_nim = "F1D022049"
        self.status_label = QLabel(f"Student: {self.student_name} | NIM: {self.student_nim}")
        self.statusBar().addPermanentWidget(self.status_label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status_time)
        self.timer.start(1000)
        self.update_status_time()

        # Setup Menu Bar
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("View")
        self.toggle_dock_action = QAction("Show Help Dock", self)
        self.toggle_dock_action.setCheckable(True)
        self.toggle_dock_action.setChecked(True)
        self.toggle_dock_action.triggered.connect(self.toggle_help_dock)
        view_menu.addAction(self.toggle_dock_action)

        # Setup QDockWidget
        self.help_dock.setFloating(False)
        self.help_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.help_text.setText(
            "Instructions:\n"
            "- Single-click to select a locker for copying.\n"
            "- Click 'Detail' to view/edit details.\n"
            "- Click 'Lock' or 'Unlock' to control locker state.\n"
            "- Click 'View Map' to see locker location.\n"
            "- Use 'Copy to Clipboard' and 'Paste from Clipboard' for locker ID.\n"
            "- Use 'Export to CSV' to save locker data."
        )
        self.help_dock.visibilityChanged.connect(self.update_dock_action_state)

        # Setup Clipboard and Buttons
        self.clipboard = QApplication.clipboard()
        self.btn_copy_clipboard.clicked.connect(self.copy_to_clipboard)
        self.btn_paste_clipboard.clicked.connect(self.paste_from_clipboard)
        self.btn_tambah_locker.clicked.connect(self.tambah_locker)
        self.btn_hapus_locker.clicked.connect(self.hapus_locker)
        self.btn_refresh.clicked.connect(self.get_all_lockers)

        # Add Export to CSV button to bottom_buttons_layout
        self.btn_export_csv = QPushButton("Export to CSV")
        self.bottom_buttons_layout.addWidget(self.btn_export_csv)
        self.btn_export_csv.clicked.connect(self.export_to_csv)

        # Setup QTableWidget with Detail, Lock, Unlock, and View Map Buttons
        self.table_lockers.setColumnCount(2)
        self.table_lockers.setHorizontalHeaderLabels(["Locker ID", "Action"])
        header = self.table_lockers.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table_lockers.setColumnWidth(0, 400)  
        self.table_lockers.setColumnWidth(1, 400) 
        self.table_lockers.itemClicked.connect(self.select_locker)
        self.table_lockers.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_lockers.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Load initial data
        self.get_all_lockers()

    def update_status_time(self):
        current_time = datetime.now().strftime("%H:%M:%S %p WITA")
        self.statusBar().showMessage(f"Time: {current_time}", 1000)

    def toggle_help_dock(self):
        if self.help_dock.isVisible():
            self.help_dock.hide()
        else:
            self.help_dock.show()

    def update_dock_action_state(self, visible):
        self.toggle_dock_action.setChecked(visible)

    def select_locker(self, item):
        row = item.row()
        self.selected_locker_id = self.table_lockers.item(row, 0).text()
        self.statusBar().showMessage(f"Selected {self.selected_locker_id} for copying", 5000)
        logger.debug(f"Selected locker ID {self.selected_locker_id} for copying")

    def copy_to_clipboard(self):
        if self.selected_locker_id:
            self.clipboard.setText(self.selected_locker_id)
            self.statusBar().showMessage(f"Copied {self.selected_locker_id} to clipboard", 5000)
            logger.debug(f"Copied locker ID {self.selected_locker_id} to clipboard")
        else:
            self.statusBar().showMessage("No locker selected", 5000)
            logger.warning("No locker selected for copy")

    def paste_from_clipboard(self):
        clipboard_text = self.clipboard.text().strip()
        if clipboard_text:
            self.input_delete_locker_id.setText(clipboard_text)
            self.statusBar().showMessage(f"Pasted {clipboard_text} into delete field", 5000)
            logger.debug(f"Pasted {clipboard_text} into delete field")
        else:
            self.statusBar().showMessage("Clipboard is empty", 5000)
            logger.warning("Clipboard is empty")

    def show_locker_details(self, row):
        locker_id = self.table_lockers.item(row, 0).text()
        for locker in self.table_lockers_data:
            if locker["lockerId"] == locker_id:
                dialog = LockerDetailDialog(locker, self)
                dialog.exec_()
                self.get_all_lockers()
                break

    def show_locker_map(self, locker_id):
        for locker in self.table_lockers_data:
            if locker["lockerId"] == locker_id:
                try:
                    dialog = MapDialog([locker], self)
                    dialog.exec_()
                except Exception as e:
                    logger.error(f"Failed to show map for locker {locker_id}: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to show map: {str(e)}")
                break

    def lock_locker(self, locker_id):
        try:
            payload = {
                "id": locker_id,
                "command": "lock"
            }
            response = requests.post("https://locker-api.vercel.app/locker/command", json=payload)
            response.raise_for_status()
            result = response.json()
            if result["success"]:
                execution_status = "The command will be executed." if result["locker"]["isRunCommand"] else "The command will not be executed."
                QMessageBox.information(self, "Success", f"{result['message']}\n{execution_status}")
                self.statusBar().showMessage(f"Command 'lock' sent for locker {locker_id}", 5000)
                logger.debug(f"Command 'lock' sent for locker {locker_id}")
                self.get_all_lockers()
            else:
                raise Exception(result["message"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to lock locker {locker_id}: {str(e)}")
            logger.error(f"Failed to send lock command: {str(e)}")

    def unlock_locker(self, locker_id):
        try:
            payload = {
                "id": locker_id,
                "command": "unlock"
            }
            response = requests.post("https://locker-api.vercel.app/locker/command", json=payload)
            response.raise_for_status()
            result = response.json()
            if result["success"]:
                execution_status = "The command will be executed." if result["locker"]["isRunCommand"] else "The command will not be executed."
                QMessageBox.information(self, "Success", f"{result['message']}\n{execution_status}")
                self.statusBar().showMessage(f"Command 'unlock' sent for locker {locker_id}", 5000)
                logger.debug(f"Command 'unlock' sent for locker {locker_id}")
                self.get_all_lockers()
            else:
                raise Exception(result["message"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to unlock locker {locker_id}: {str(e)}")
            logger.error(f"Failed to send unlock command: {str(e)}")

    def get_all_lockers(self):
        try:
            response = requests.get("https://locker-api.vercel.app/locker/all")
            response.raise_for_status()
            data = response.json()
            if data["success"]:
                self.table_lockers.setRowCount(0)
                self.table_lockers_data = data["lockers"]
                for locker in self.table_lockers_data:
                    row = self.table_lockers.rowCount()
                    self.table_lockers.insertRow(row)
                    self.table_lockers.setItem(row, 0, QTableWidgetItem(locker["lockerId"]))
                    # Create a main vertical layout to align buttons to the top
                    main_layout = QVBoxLayout()
                    main_layout.setContentsMargins(0, 0, 0, 0)
                    main_layout.setSpacing(0)
                    action_layout = QHBoxLayout()
                    action_layout.setSpacing(2)
                    action_widget = QWidget()
                    action_widget.setLayout(main_layout)

                    # Detail button
                    detail_button = QPushButton("Detail")
                    detail_button.setMinimumHeight(30) 
                    detail_button.setMaximumWidth(70)   
                    detail_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                    detail_button.setToolTip("View and edit locker details")
                    font = QFont("Segoe UI", 12)  
                    detail_button.setFont(font)
                    detail_button.clicked.connect(lambda _, r=row: self.show_locker_details(r))
                    action_layout.addWidget(detail_button)

                    # Lock button
                    lock_button = QPushButton("Lock")
                    lock_button.setMinimumHeight(30) 
                    lock_button.setMaximumWidth(70)   
                    lock_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                    lock_button.setObjectName("lock_button")
                    lock_button.setToolTip("Lock the locker")
                    lock_button.setFont(font)
                    lock_button.clicked.connect(lambda _, lid=locker["lockerId"]: self.lock_locker(lid))
                    action_layout.addWidget(lock_button)

                    # Unlock button
                    unlock_button = QPushButton("Unlock")
                    unlock_button.setMinimumHeight(30)  
                    unlock_button.setMaximumWidth(70)  
                    unlock_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                    unlock_button.setToolTip("Unlock the locker")
                    unlock_button.setObjectName("unlock_button")
                    unlock_button.setFont(font)
                    unlock_button.clicked.connect(lambda _, lid=locker["lockerId"]: self.unlock_locker(lid))
                    action_layout.addWidget(unlock_button)

                    # View Map button
                    map_button = QPushButton("View Map")
                    map_button.setMinimumHeight(30)  
                    map_button.setMaximumWidth(70)   
                    map_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                    map_button.setToolTip("View locker location on map")
                    map_button.setObjectName("map_button")
                    map_button.setFont(font)
                    map_button.clicked.connect(lambda _, lid=locker["lockerId"]: self.show_locker_map(lid))
                    action_layout.addWidget(map_button)

                    main_layout.addLayout(action_layout)
                    main_layout.addStretch()
                    self.table_lockers.setCellWidget(row, 1, action_widget)
                    self.table_lockers.setRowHeight(row, 50) 
                self.statusBar().showMessage(f"Loaded {len(data['lockers'])} lockers", 5000)
                logger.debug(f"Loaded {len(data['lockers'])} lockers")
                self.selected_locker_id = None
        except Exception as e:
            logger.error(f"Failed to fetch lockers: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to fetch lockers: {str(e)}")

    def tambah_locker(self):
        try:
            response = requests.post("https://locker-api.vercel.app/locker/register")
            response.raise_for_status()
            if response.json()["success"]:
                self.get_all_lockers()
                self.statusBar().showMessage("Locker added successfully", 5000)
        except Exception as e:
            logger.error(f"Failed to add locker: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to add locker: {str(e)}")

    def hapus_locker(self):
        locker_id = self.input_delete_locker_id.text().strip()
        if not locker_id:
            QMessageBox.warning(self, "Error", "Please paste a locker ID")
            return
        try:
            response = requests.delete(f"https://locker-api.vercel.app/locker/delete/{locker_id}")
            response.raise_for_status()
            if response.json()["success"]:
                self.get_all_lockers()
                self.input_delete_locker_id.clear()
                self.statusBar().showMessage("Locker deleted successfully", 5000)
        except Exception as e:
            logger.error(f"Failed to delete locker: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to delete locker: {str(e)}")

    def export_to_csv(self):
        if not self.table_lockers_data:
            QMessageBox.information(self, "Info", "No data to export")
            return
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
            if file_path:
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.table_lockers_data[0].keys())
                    writer.writeheader()
                    for locker in self.table_lockers_data:
                        writer.writerow(locker)
                QMessageBox.information(self, "Success", "Exported to CSV successfully")
        except Exception as e:
            logger.error(f"Failed to export to CSV: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to export to CSV: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        with open("styles.qss", "r") as style_file:
            app.setStyleSheet(style_file.read())
    except Exception as e:
        logger.error(f"Failed to load stylesheet: {str(e)}")
        QMessageBox.warning(None, "Warning", f"Failed to load stylesheet: {str(e)}")
    window = LockerApp()
    window.show()
    sys.exit(app.exec_())