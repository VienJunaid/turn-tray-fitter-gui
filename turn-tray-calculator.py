# Python Script for the Turn Tray Fitter GUI 

# Structure
# JSON File containing all Model ID, Dimensions(L*W*H)
#
#
# Python Script
# 1. Read the Model ID in the command line 
# 2. Check if this model exists first
# 3. If model exists, then ask for dimensions and shape of object USER is trying to insert into freezer
# 4. Calculate area and volume of the freezer
# 5. Calculate how many "objects" can fit inside the freezer (horizontal and vertical layer) 
# 6. Output results (fit count)

import math 
import json
import os
import sys 
from PyQt6.QtWidgets import QComboBox, QApplication, QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class Screen1(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout() 
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) 

        # MVE LOGO 
        logo = QLabel() 
        pixmap = QPixmap("MVE logos/white_logo.png")
        pixmap = pixmap.scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title 
        title = QLabel("Turn Tray Estimation Fitter")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #ffffff; margin-bottom: 8px;")
       
        # Subtitles
        subtitle = QLabel("Enter a Freezer Model ID to begin")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        subtitle.setStyleSheet("font-size: 13px; color: #6a8ab0; margin-bottom: 24px")

        # Model ID input
        self.model_input = QLineEdit() 
        self.model_input.setPlaceholderText("Enter Freezer Model ID")

        # Start button 
        start_btn = QPushButton("Start")
        start_btn.setStyleSheet(""" 
        QPushButton {
            background-color: #ffffff;
            color: #0a1628;
            border: none;
            border-radius: 10px;
            padding: 10px 0px;
            font-size: 15px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 1px;
        }
        QPushButton:hover {
            background-color: #dce8ff;
        }
        QPushButton:pressed {
            background-color: #b0c8f0;
        }
        """)
        start_btn.clicked.connect(self.on_start) # Function call here after button press  
        
        # Layout 
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(subtitle) 
        layout.addWidget(self.model_input)
        layout.addWidget(start_btn)
        self.setLayout(layout) 
   
    # Function when start button is pressed 
    def on_start(self):
        model_id = self.model_input.text().strip() 
        json_path = os.path.join(directory, "freezer_models.json")

        if not json_checker(json_path):
            QMessageBox.critical(self, "Error", "freezer_models.json not found")
            return 
        try:
            self.parent.freezer = load_freezer(model_id, json_path) # load freezer data 
            self.parent.stack.setCurrentIndex(1)
        except KeyError as e:
            QMessageBox.critical(self, "Error", str(e))

class Screen2(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent 

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # MVE Logo
        logo = QLabel() 
        pixmap = QPixmap("MVE logos/white_logo.png")
        pixmap = pixmap.scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title 
        title = QLabel("Select a shape and fill in the dimensions")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #ffffff; margin-bottom: 8px;")


        # Shape dropdown 
        shape_label = QLabel("Select Shape:")
        self.shape_dropdown = QComboBox() 
        self.shape_dropdown.addItems(["Cylinder", "Cube", "Rectangle"])
        self.shape_dropdown.currentIndexChanged.connect(self.on_shape_changed)

        self.dim_layout = QVBoxLayout() 

        calc_btn = QPushButton("Calculate")
        calc_btn.setStyleSheet(""" 
        QPushButton {
            background-color: #ffffff;
            color: #0a1628;
            border: none;
            border-radius: 10px;
            padding: 10px 0px;
            font-size: 15px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 1px;
        }
        QPushButton:hover {
            background-color: #dce8ff;
        }
        QPushButton:pressed {
            background-color: #b0c8f0;
        }
        """)
        calc_btn.clicked.connect(self.on_calculate)

        layout.addWidget(logo)
        #layout.setSpacing(10) # 16 px gap between all widgets 
        layout.addWidget(title) 
        layout.addWidget(shape_label)      
        layout.addWidget(self.shape_dropdown)
        layout.addLayout(self.dim_layout)
        layout.addWidget(calc_btn)
        self.setLayout(layout) 

        self.on_shape_changed(0) # default fields for first shape 
    
    # Helper Function for Screen 2
    def on_shape_changed(self, index): 
        # clear existing dimensions field 
        while self.dim_layout.count():
            item = self.dim_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if index == 0: 
            self.radius_input = QLineEdit() 
            self.radius_input.setPlaceholderText("Radius (mm)")
            self.height_input = QLineEdit() 
            self.height_input.setPlaceholderText("Height (mm)")
            self.dim_layout.addWidget(self.radius_input)
            self.dim_layout.addWidget(self.height_input)

        elif index == 1: # Cube 
            self.side_input = QLineEdit() 
            self.side_input.setPlaceholderText("Side Length (mm)")
            self.dim_layout.addWidget(self.side_input)

        elif index == 2:
            self.length_input = QLineEdit() 
            self.length_input.setPlaceholderText("Length (mm)")
            self.width_input = QLineEdit() 
            self.width_input.setPlaceholderText("Width (mm)")
            self.height_input = QLineEdit() 
            self.height_input.setPlaceholderText("Height (mm)")
            self.dim_layout.addWidget(self.length_input)
            self.dim_layout.addWidget(self.width_input)
            self.dim_layout.addWidget(self.height_input)

    
    def on_calculate(self):
        index = self.shape_dropdown.currentIndex()

        if index == 0:
            dims = (float(self.radius_input.text()), float(self.height_input.text()))
            shape = "C"
        elif index == 1:
            dims = (float(self.side_input.text()),)
            shape = "S"
        elif index == 2:
            dims = (float(self.length_input.text()), float(self.width_input.text()), float(self.height_input.text()))
            shape = "R"

        result = allocate_single_type(self.parent.freezer, shape, dims) 
        self.parent.screen3.set_result(result["total_capacity"])
        self.parent.stack.setCurrentIndex(2)


class Screen3(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent 

        layout = QVBoxLayout() 
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # MVE Logo 
        logo = QLabel() 
        pixmap = QPixmap("MVE logos/white_logo.png")
        pixmap = pixmap.scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Result Label 
        self.result_label = QLabel("Total Capacity: --") 
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #ffffff; margin-bottom: 8px;")

        # Calculate again button 
        again_btn = QPushButton("Calculate Again")
        again_btn.setStyleSheet(""" 
        QPushButton {
            background-color: #ffffff;
            color: #0a1628;
            border: none;
            border-radius: 10px;
            padding: 10px 0px;
            font-size: 15px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 1px;
        }
        QPushButton:hover {
            background-color: #dce8ff;
        }
        QPushButton:pressed {
            background-color: #b0c8f0;
        }
        """)
        again_btn.clicked.connect(self.on_calculate_again)

        layout.addWidget(logo)
        layout.addWidget(self.result_label)
        layout.addWidget(again_btn)
        self.setLayout(layout) 
    
    def set_result(self, total_capacity):
        self.result_label.setText(f"Total Capacity: {total_capacity} objects")
    
    def on_calculate_again(self):
        self.parent.stack.setCurrentIndex(0) # go back to screen 1 


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Turn Tray Fitter") 
        self.setMinimumSize(480, 600) 
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0a1628;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                }
                QLabel {
                    color: #ffffff
                }
                QLineEdit, QComboBox {
                    background-color: #152642;
                    color: #ffffff;
                    border: 1px solid #2a4a7f;
                    border-radius: 6px;
                    padding: 10px 14px; 
                    font-size: 14px; 
                }
                QLineEdit:focus, QComboBox: focus {
                    border: 1px solid #4a90d9;
                }
                QLineEdit: placeholder {
                    color: #6a8ab0;
                }
                QPushButton {
                    background-color: #ffffff; 
                    color: #0a1628;
                    border: none;
                    border-radius: 10px;
                    padding: 12px 0px; 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    font-size: 14px
                    font-weight: bold; 
                }
                QPushButton:hover {
                    background-color: #dce8ff;
                }
                QPushButton:pressed {
                    background-color: #b0c8f0; 
                }
                QComboBox::drop-down {
                    border: none; 
                    padding-right: 10px; 
                }
                QComboBox QAbstractItemView {
                    background-color: #152642;
                    color: #ffffff;
                    selection-background-color: #2a5298;
                    border: 1px solid #2a4a7f;
                }
            """)

        self.freezer = None # Store loaded freezer dict so all screens can access it
        
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        self.screen1 = Screen1(self)
        self.screen2 = Screen2(self)
        self.screen3 = Screen3(self)

        self.stack.addWidget(self.screen1)
        self.stack.addWidget(self.screen2)
        self.stack.addWidget(self.screen3) 

        self.stack.setCurrentIndex(0) # Start on screen 1


directory = '' # Location of JSON files 

GAP = 3.175 # everything is in milimeters mm 

def load_freezer(model_id, json_path): 
    with open(json_path, 'r') as file:
        data = json.load(file) 
    
    for model in data["models"]:
        if model["model_id"] == model_id:
            return model
    raise KeyError("Freezer Model is not found in database.")


def json_checker(json_path):
    if not os.path.isfile(json_path):
        return False
    return True

# --- HORIZONTAL PACKING: CYLINDERS ---

def pack_circles_in_circle(R_eff, r_eff): 
    count = 0

    if r_eff <= R_eff:
        count += 1

    k = 1
    while True:
        r_k = 2 * k * r_eff 
        if r_k + r_eff > R_eff:
            break 
        count += math.floor((2 * math.pi * r_k) / (2 * r_eff))
        k += 1
    return count



# --- HORIZONTAL PACKING: CUBES & RECT PRISMS ---

def pack_rects_in_circle(R_eff, l_eff, w_eff):
    best_count = 0

    for ox, oy in [(0, 0), (l_eff / 2, w_eff / 2)]:
        count = 0
        x = -R_eff + ox
        while x <= R_eff:
            y = -R_eff + oy
            while y <= R_eff:
                corners = [
                    (x - l_eff / 2, y - w_eff / 2),
                    (x + l_eff / 2, y - w_eff / 2),
                    (x - l_eff / 2, y + w_eff / 2),
                    (x + l_eff / 2, y + w_eff / 2),
                ]
                if all(math.sqrt(cx**2 + cy**2) <= R_eff for cx, cy in corners):
                    count += 1
                y += w_eff
            x += l_eff
        best_count = max(best_count, count)

    return best_count


# --- SAFETY MARGIN ---

def apply_horizontal_safety_margin(count):
    return max(0, count - 1) 


# --- VERTICAL STACKING ---

def layers_available(H_usable, h_eff):
    return math.floor(H_usable / h_eff) 


# --- SHAPE NORMALIZATION ---

def normalize_to_footprint(shape, dims):
    if shape == "C":
        r, h = dims
        return ("circle", r + GAP / 2, h + GAP)
    elif shape == "S":
        s = dims[0]
        return ("rectangle", (s + GAP, s + GAP), s + GAP)
    elif shape == "R":
        l, w, h = dims
        return ("rectangle", (l + GAP, w + GAP), h + GAP)


# --- ALLOCATION ---

def allocate_single_type(freezer, shape, dims):
    R_eff = freezer["R"] - GAP
    H_usable = freezer["H"] - freezer["handle_bar_clearance"]

    footprint_type, footprint_dims_eff, h_eff = normalize_to_footprint(shape, dims)

    if footprint_type == "circle":
        raw_count = pack_circles_in_circle(R_eff, footprint_dims_eff)
    else:
        l_eff, w_eff = footprint_dims_eff
        raw_count = pack_rects_in_circle(R_eff, l_eff, w_eff)

    objects_per_layer = apply_horizontal_safety_margin(raw_count)
    num_layers = layers_available(H_usable, h_eff)
    total_fit = objects_per_layer * num_layers

    return { "total_capacity": total_fit } 

# FUTURE (not v1): allocate_multi_type for mixed shapes in one freezer
# def allocate_multi_type(freezer, object_list):
#   - open question #3: whole-layer-per-type (v1 default) vs mixed-type-per-layer
#   - for v1: loop over each type, call allocate_single_type, sum totals
#   pass

def main():
    # Enter the Model ID in the command line 
    model_id = input("Enter the Freezer Model ID: ")

    # Call a checker function to check if this exists 
    json_path = os.path.join(directory, "freezer_models.json")
    
    if not json_checker(json_path):
        print("JSON file containing all the freezer models is missing.")
        return

    # Loading Freezer to get Freezer dict  
    try:
        freezer = load_freezer(model_id, json_path)
    except KeyError as e:
        print(e) 
        return

    # ask for the shape the user is trying to insert into freezer 
    user_shape = input("What shape are you trying to put into the freezer?: (C: Cylinder, S: Square (cube), R: Rectangle) ")
    
    match user_shape:
        case "C":
            radius = input("Radius of Cylinder: ")
            height = input("Height of Cylinder: ")
            dimensions = (float(radius), float(height))
        case "S":
            sides = input("Give us the length of the square: ")
            dimensions = (float(sides),)
        case "R":
            length = input("Length of Rectangle: ")
            width = input ("Width of Rectangle: ")
            height = input("Height of Rectangle: ")
            dimensions = (float(length), float(width), float(height)) 
        case _:
            print("Must be either: C, S, or R") 
            return 

    result = allocate_single_type(freezer, user_shape, dimensions)
    print(f"Total freezer capacity for this object: {result['total_capacity']}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow() 
    window.show()
    sys.exit(app.exec())


