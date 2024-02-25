from PyQt5 import  uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QMessageBox, QFileDialog, QShortcut
from PyQt5.QtCore import Qt, QTimer
import numpy as np
import pyqtgraph as pg
from scipy.signal import freqz, lfilter, zpk2tf
import pandas as pd
import math
import os


class DigitalFilterDesigner(QMainWindow):
    def __init__(self):
        super(DigitalFilterDesigner, self).__init__()
        uic.loadUi("./GUIs/digitalFilterDesigner.ui", self)
        self.show()
        

        self.plots = [self.unitCirclePlot, self.magnitudeResponsePlot, self.phaseResponsePlot,
                          self.allPassPlot, self.mouseInputPlot, self.mouseFilteredOutput, self.mouseInputSignalPlot]

        self.ptr, self.signal_speed, self.playing = 0, 1, False


        self.x_last_pos, self.y_last_pos = None, None
        self.x_last_pair, self.y_last_pair = None, None
        self.point_movement, self.point_selected = None, False
        

        self.zero_pole_data = { "Zeros": [], "Poles": [] }



        self.data, self.data_filtered = [], []

        self.signalItemInput, self.signalItemFiltered = pg.PlotDataItem([], pen = 'y', width = 2), pg.PlotDataItem([], pen = 'y', width = 2)

        self.mouseInputPlot.addItem(self.signalItemInput)
        self.mouseFilteredOutput.addItem(self.signalItemFiltered)

    

        self.pair_selected = None

        self.data_loaded = False

        self.selected = "Zeros"

        self.mouse_loc_circle = None

        self.move_clicked = False


        self.checked_coeffs = [0.0]
        self.total_phase = 0

        self.frequencies = 0
        self.magnitude_response = 0
        self.phase_response = 0
        

        self.colors = ['#FFA500', '#FFFF00', '#FF0000', '#00FF00', '#00FFFF', '#0000FF', '#800080', '#FF00FF', '#FF1493', '#00FF7F', '#FFD700', '#FF6347', '#48D1CC', '#8A2BE2', '#20B2AA']


        [container.setVisible(False) for container in [self.mouseInputSignalPlot, self.mouseInputLabel, self.spacer1, self.spacer2, self.spacer3]]

        [self.plot_settings(plot) for plot in self.plots]




        # self.addZeroRadioButton.toggled.connect(self.toggle_pole_zero)
        # self.addPoleRadioButton.toggled.connect(self.toggle_pole_zero)
        self.allPassEnableCheckbox.stateChanged.connect(self.toggle_all_pass)
        
        self.removeAllZeroes.clicked.connect(lambda: self.clear_points("Zeros"))
        self.removeAllPoles.clicked.connect(lambda: self.clear_points("Poles"))
        self.removeAllButton.clicked.connect(lambda: self.clear_points("All"))
        self.addAllpassButton.clicked.connect(self.add_coefficient)
        self.removeAllpassButton.clicked.connect(self.remove_coefficient)
        self.loadSignalButton.clicked.connect(self.load_signal)
        self.playButton.clicked.connect(self.play_pause_handler)

        self.speedSlider.valueChanged.connect(self.change_signal_speed)
        
        self.check_zero_radio_button()

        self.actionImport.triggered.connect(self.load_filter)
        self.actionExport.triggered.connect(self.save_filter)

        self.enableMouseInputCheckbox.stateChanged.connect(self.toggle_mouse_plot)

        self.allpassTable.itemChanged.connect(self.update_allpass_plot)

        self.clearButton.clicked.connect(self.clear_plots)

        

        # Create circle ROIs to show the unit circle and an additional circle of radius 2 
        self.roi_unitCircle = pg.CircleROI([-1, -1], [2, 2], pen=pg.mkPen('g',width=2), movable=False, resizable=False, rotatable = False)
        
            
        # Set the origin point to the center of the widget
        self.unitCirclePlot.setYRange(-1.1, 1.1, padding=0)
        self.unitCirclePlot.setXRange(-1.1, 1.1, padding=0)
        self.unitCirclePlot.setMouseEnabled(x=False, y=False)


        self.unitCirclePlot.addItem(self.roi_unitCircle)    
        self.roi_unitCircle.removeHandle(0)

        self.unitCirclePlot.scene().sigMouseClicked.connect(self.unit_circle_click_handler)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_handler)

        self.mouse_signal_ptr = 1
    

        self.mouseInputSignalPlot.scene().sigMouseMoved.connect(self.mouse_movement_handler)

        self.unitCirclePlot.scene().sigMouseMoved.connect(self.change_point_pos)

        save_shortcut_z = QShortcut(Qt.Key_Z, self)
        save_shortcut_z.activated.connect(self.check_zero_radio_button)

        save_shortcut_p = QShortcut(Qt.Key_P, self)
        save_shortcut_p.activated.connect(self.check_pole_radio_button)


    def plot_settings(self, plot):
        plot.getPlotItem().showGrid(True, True)
        plot.setMenuEnabled(False)
        
    
#--------------------------------------- Signal in Cine Mode ----------------------------------------------
        
    def change_signal_speed(self):
        self.signal_speed = int(self.speedSlider.value())
        self.speedLabel.setText(f"Speed: {self.signal_speed}")



    def pause_signal(self):
        self.timer.stop()
        self.playing = False
        self.playButton.setText("Play")


    
    def play_pause_handler(self):
        self.playing = not self.playing
    
        if self.playing:
            self.filter_data()
            if self.ptr >= len(self.data)-1:
                self.ptr = 0
                self.reset_viewport_range()

            self.timer.start(30)
            self.playing = True
            self.playButton.setText("Stop")

        else:
            self.pause_signal()



    def update_handler(self):
        _ , x_max = self.plots[4].viewRange()[0]
        self.signalItemInput.setData(self.data[0:self.ptr])
        self.signalItemFiltered.setData(self.data_filtered[0:self.ptr])

        if self.ptr > x_max:   
            for plot in [self.mouseInputPlot, self.mouseFilteredOutput]:
                plot.setLimits(xMax = self.ptr)
                plot.getViewBox().translateBy(x = self.signal_speed)
       
        if self.ptr >= len(self.data)-1:
            self.pause_signal()
        
        self.ptr += self.signal_speed
        QApplication.processEvents()

        
#----------------------------------------------- All Pass Filter Coefficients ----------------------------------------------------------------
    def add_coefficient(self):
        coeff_item = QTableWidgetItem(self.allpassCombobox.currentText())
        coeff_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        coeff_item.setCheckState(Qt.CheckState.Checked)

        self.allpassTable.insertRow(self.allpassTable.rowCount())
        row = self.allpassTable.rowCount() - 1
        self.allpassTable.setItem(row, 0, coeff_item)
        
        self.update_allpass_plot()
        
        
    def remove_coefficient(self):
        self.allpassTable.removeRow(self.allpassTable.currentRow()) 

        self.update_allpass_plot()
        

       
    
    #------------------------------------------------------- Load and Save Filters --------------------------------------------------------------
        
    def save_filter(self):
        try:
            # Path for the saved filter
            script_directory = os.path.dirname(os.path.abspath(__file__))
            initial_folder = os.path.join(script_directory, "Zeros-Poles")

            path, _ = QFileDialog.getSaveFileName(self, 'Save File', initial_folder, "CSV files (*.csv)")

            if path:
                # Ensure zeros and poles have the same length by padding with None
                max_len = max(len(self.zero_pole_data["Zeros"]), len(self.zero_pole_data["Poles"]))
                zeros_padded = self.zero_pole_data["Zeros"] + [None] * (max_len - len(self.zero_pole_data["Zeros"]))
                poles_padded = self.zero_pole_data["Poles"] + [None] * (max_len - len(self.zero_pole_data["Poles"]))

                df = pd.DataFrame({
                    'Zeros_x': [zero.x() if zero else None for zero in zeros_padded],
                    'Zeros_y': [zero.y() if zero else None for zero in zeros_padded],
                    'Poles_x': [pole.x() if pole else None for pole in poles_padded],
                    'Poles_y': [pole.y() if pole else None for pole in poles_padded],
                })

                df.to_csv(path, index=False)

        except Exception as e:
            print(f"Error: {e}")



    def load_filter(self):
        try:
            # Clear Existing Zeros and Poles data
            self.zero_pole_data["Zeros"] = []
            self.zero_pole_data["Poles"] = []

            script_directory = os.path.dirname(os.path.abspath(__file__))
            initial_folder = os.path.join(script_directory, "Zeros-Poles")

            path, _ = QFileDialog.getOpenFileName(self, 'Open File', initial_folder, "CSV files (*.csv)")

            if path:
                df = pd.read_csv(path)

                if len(df['Zeros_x']) != len(df['Zeros_y']) or len(df['Poles_x']) != len(df['Poles_y']):
                    print("Error: Zeros and Poles arrays must be of the same length.")
                    return

                for x, y in zip(df['Zeros_x'], df['Zeros_y']):
                    if x is not None and y is not None and not (math.isnan(x) or math.isnan(y)):
                        point = pg.Point(x, y)
                        self.zero_pole_data["Zeros"].append(point)

                for x, y in zip(df['Poles_x'], df['Poles_y']):
                    if x is not None and y is not None and not (math.isnan(x) or math.isnan(y)):
                        point = pg.Point(x, y)
                        self.zero_pole_data["Poles"].append(point)

                self.update_unit_circle_plot()

        except Exception as e:
            print(f"Error: {e}")




# ------------------------------------------------- Hide/Show Mouse Input Plot -------------------------------------------------------------
    def toggle_mouse_plot(self):
        mouse_containers = [self.mouseInputSignalPlot, self.mouseInputLabel, self.spacer1, self.spacer2, self.spacer3]
        other_containers = [self.speedSlider, self.speedLabel, self.playButton, self.clearButton, self.loadSignalButton, self.spacer4]

        visibility_mouse = self.enableMouseInputCheckbox.isChecked()
        visibility = (True, False) if visibility_mouse else (False, True)

        for container in mouse_containers:
            container.setVisible(visibility_mouse)
        for container in other_containers:
            container.setVisible(visibility[1])

        self.reset_viewport_range()

#---------------------------------------------------- Load Signal ----------------------------------------------------------------------------
        
    def load_signal(self):
        try:
            self.clear_plots()
            script_directory = os.path.dirname(os.path.abspath(__file__))
            initial_folder = os.path.join(script_directory, "Data")

            path, _ = QFileDialog.getOpenFileName(
                self, 'Open File', initial_folder, "CSV files (*.csv)"
            )
            
            if not path:
                return

            df = pd.read_csv(path)

            self.data = df['Data'].values

            self.data_filtered = self.data.copy()

            self.data_loaded = True

            self.reset_viewport_range()
            self.signalItemInput.setData(self.data[0:self.ptr])
            self.signalItemFiltered.setData(self.data_filtered[0:self.ptr])

        except Exception as e:
            print(f"Error: {e}")


# ------------------------------------------------------- clicks -----------------------------------------------------------------
            
    def unit_circle_click_handler(self, event):
        # if left click
        if event.button() == Qt.LeftButton:
            # if CTRL is pressed with the left click add new zero/pole
            if event.modifiers() == Qt.ControlModifier:
                print("CTRL")
                point_mode = "Zeros" if self.addZeroRadioButton.isChecked() else "Poles"
                self.add_point(self.mouse_loc_circle, point_mode)
                self.update_unit_circle_plot()
            else:
                print("ELSE")
                # CTRL Was not pressed so just drag the zero/pole
                self.move_clicked = True
                self.move_point(self.mouse_loc_circle)

        elif event.button() == Qt.RightButton:
            # if right click then new place for the zero/pole
            if self.x_last_pos is not None and self.point_selected:
                self.unselect_moving_point()
            else:
                # Remove zero/pole
                self.remove_point(self.mouse_loc_circle)

        self.set_filtered_data(self.ptr)

    def set_filtered_data(self, pointer):
        self.filter_data()
        self.signalItemInput.setData(self.data[:pointer])
        self.signalItemFiltered.setData(self.data_filtered[:pointer])
                
    


    def unselect_moving_point(self):
        self.remove_point(self.point_movement)
        point = pg.Point(self.x_last_pos, self.y_last_pos)
        self.add_point(point, self.selected)
        if self.pair_selected:
            self.remove_point(self.pair_point_movement)
            point = pg.Point(self.x_last_pos, -self.y_last_pos)
            self.add_point(point, self.selected)
        self.update_unit_circle_plot()
        self.x_last_pos, self.y_last_pos, self.point_selected, self.pair_selected, self.move_clicked = None, None, False, False, False



    def move_point(self, pos_data):
        if self.x_last_pos is not None and self.point_selected:
            self.x_last_pos, self.y_last_pos, self.point_selected, self.pair_selected, self.move_clicked = None, None, False, False, False

        else:
            for dict_name in ["Zeros", "Poles"]:
                self.move_point_from_list(dict_name, pos_data)



    def move_point_from_list(self, dict_name, point_data):
        point_list = self.zero_pole_data[dict_name].copy()
        for point in point_list:
            if np.allclose([point.x(), point.y()], [point_data.x(), point_data.y()], atol=0.03):
                self.x_last_pos, self.y_last_pos = point.x(), point.y()
                point_pair = pg.Point(point.x(), -point.y())

                self.selected = dict_name
                
                self.point_selected = True
                if point_pair in self.zero_pole_data[self.selected]:
                    self.pair_selected = True

                self.point_movement = pg.Point(self.x_last_pos, self.y_last_pos)
                self.pair_point_movement = pg.Point(self.x_last_pos, -self.y_last_pos)
                break

    def change_point_pos(self, pos):
        pos = self.unitCirclePlot.getViewBox().mapSceneToView(pos)

        self.mouse_loc_circle = pg.Point(pos.x(), pos.y())
        self.mouse_loc_circle_pair = pg.Point(pos.x(), -pos.y())
        if self.move_clicked and self.point_selected:
            self.remove_point(self.point_movement)
            self.add_point(self.mouse_loc_circle, self.selected)
            if self.pair_selected:
                self.remove_point(self.pair_point_movement)
                self.add_point(self.mouse_loc_circle_pair, self.selected)

            self.update_unit_circle_plot()
            self.point_movement = self.mouse_loc_circle
            self.pair_point_movement = self.mouse_loc_circle_pair

        self.set_filtered_data(self.ptr)


# -------------------------------------------------- Adding Point ------------------------------------------------------------------------
                
    def add_point(self, point, type):
        point = pg.Point(point.x(), point.y())

        if self.pairModeCheckbox.isChecked():
            point_pair = pg.Point(point.x(), -point.y())
            self.zero_pole_data[type].append(point_pair)

        self.zero_pole_data[type].append(point)


# --------------------------------------------------- Removing Point ---------------------------------------------------------------------
        
    def remove_point(self, point_data):
        for dict_name in ["Zeros", "Poles"]:
            if self.remove_point_from_list(self.zero_pole_data[dict_name], point_data, atol_cof = 0):
                break
            elif self.remove_point_from_list(self.zero_pole_data[dict_name], point_data):
                break

        
    def remove_point_from_list(self, point_list, point_data, atol_cof = 0.03):
        for point in point_list.copy():
            if np.allclose([point.x(), point.y()], [point_data.x(), point_data.y()], atol = atol_cof):
                point_list.remove(point)
                point_pair = pg.Point(point.x(), -point.y())
                if point_pair in point_list:
                    point_list.remove(point_pair)
                self.update_unit_circle_plot()
                return True
        self.update_unit_circle_plot()
        return False

    
    def clear_plots(self):
        self.data = [0, 0]
        self.data_filtered = [0, 0]
        self.signalItemInput.setData([0])
        self.signalItemFiltered.setData([0])
        self.ptr = 0
        


    def update_unit_circle_plot(self):
        self.unitCirclePlot.clear()

        for point_type in ["Zeros", "Poles"]:
            self.plot_points(self.zero_pole_data[point_type], point_type)

        self.unitCirclePlot.addItem(self.roi_unitCircle)

        self.update_response_plots()
        self.update_allpass_plot()



    def plot_points(self, data, point_type):
        for point in data:
            brush = 'b' if point_type == "Zeros" else 'r'
            symbol = 'o' if point_type == "Zeros" else 'x'
            point_plot = pg.ScatterPlotItem(pos=[(point.x(), point.y())], brush = brush, size = 10, symbol = symbol)
            self.unitCirclePlot.addItem(point_plot)
        


# ------------------------------------------------------- Update Magnitude and Phase Response -------------------------------------------

    def update_response_plots(self):
        z, p, z_allpass, p_allpass = self.get_all_pass_filter()

        w, h = freqz(np.poly(z), np.poly(p))
        self.frequencies, self.magnitude_response, self.phase_response = w, np.abs(h), self.fix_phase(h)

        self.plot_response(self.magnitudeResponsePlot, self.frequencies, self.magnitude_response, pen='b', label='Magnitude', units='Gain', unit_bot = "Radian")

        self.plot_response(self.phaseResponsePlot, self.frequencies, self.phase_response, pen='r', label='Phase', units='Degree', unit_bot = "Radian" , name = "Normal Phase Response")

        if self.allPassEnableCheckbox.isChecked():        
            w, h = freqz(np.poly(z_allpass), np.poly(p_allpass))
            self.frequencies, self.magnitude_response, self.phase_response = w, np.abs(h), self.fix_phase(h)
            self.phaseResponsePlot.plot(x=self.frequencies, y=self.phase_response, pen='y', name = "AllPass Phase Response")


    def plot_response(self, plot, x, y, pen, label, units, unit_bot, name = ""):
        plot.clear()
        plot.plot(x, y, pen = pen, name = name)
        plot.setLabel('left', label, units = units)
        plot.setLabel('bottom', label, units = unit_bot)
        self.phaseResponsePlot.addLegend()


    
    def fix_phase(self, h):
        phase_response_deg = np.rad2deg(np.angle(h))
        phase_response_constrained  = np.where(phase_response_deg < 0, phase_response_deg + 360, phase_response_deg)
        phase_response_constrained  = np.where(phase_response_constrained  > 180, phase_response_constrained  - 360, phase_response_constrained )
        
        return phase_response_constrained 
    
# ---------------------------------------------------------- Check the allpass filter -----------------------------------------------------------
    
    def get_all_pass_filter(self):
        self.checked_coeffs = [0.0]
    
        if self.allPassEnableCheckbox.isChecked():
            for row in range(self.allpassTable.rowCount()):
                item = self.allpassTable.item(row, 0)
                if item and item.checkState() == Qt.CheckState.Checked:
                    self.checked_coeffs.append(float(item.text())) 

        self.all_pass_zeros = self.zero_pole_data["Zeros"].copy()
        self.all_pass_poles = self.zero_pole_data["Poles"].copy()

        w, all_pass_phs = 0, 0
        self.allPassPlot.clear()

        for i in range(len(self.checked_coeffs)):
            a = self.checked_coeffs[i]

            if a == 1:
                a= 0.9999999
                
            a = complex(a, 0)
            
            if a != 0:
                a_conj = 1 / np.conj(a)

                w, h = freqz([-np.conj(a), 1.0], [1.0, -a])
                all_pass_phs = np.add(np.angle(h), all_pass_phs)
                self.allPassPlot.plot(w, np.angle(h), pen=self.colors[i % len(self.colors)], name = f'All pass{a.real}')
                self.allPassPlot.setLabel('left', 'All Pass Phase', units='degrees')
                
                self.all_pass_poles.append(pg.Point(a.real, a.imag))
                self.all_pass_zeros.append(pg.Point(a_conj.real, a_conj.imag))
        
        self.unitCirclePlot.clear()
        self.plot_points(self.all_pass_zeros, "Zeros")
        self.plot_points(self.all_pass_poles, "Poles")
        self.unitCirclePlot.addItem(self.roi_unitCircle)

        
        if len(self.checked_coeffs) > 1:
            self.allPassPlot.plot(w, all_pass_phs, pen=self.colors[-1], name = 'All pass Total')
        self.allPassPlot.addLegend()

        # Combine zeros and poles
        z_allpass = np.array([complex(zero.x(), zero.y()) for zero in self.all_pass_zeros])
        p_allpass = np.array([complex(pole.x(), pole.y()) for pole in self.all_pass_poles])

        z = np.array([complex(zero.x(), zero.y()) for zero in self.zero_pole_data["Zeros"]])
        p = np.array([complex(pole.x(), pole.y()) for pole in self.zero_pole_data["Poles"]])

        return z, p, z_allpass, p_allpass
    

    def update_allpass_plot(self):
        self.update_response_plots()
        _, _, z, p = self.get_all_pass_filter()
        # Calculate frequency response
        _, h = freqz(np.poly(z), np.poly(p))
        self.phase_response = self.fix_phase(h)
    

    def filter_data(self):
        _,_, z, p = self.get_all_pass_filter()
        numerator, denominator = zpk2tf(z, p, 1)
        self.data_filtered = np.real(lfilter(numerator, denominator, self.data))
  





#------------------------------------------------------- Draw By Mouse Movement -------------------------------------------------------------------
    def mouse_movement_handler(self, pos):
        if self.enableMouseInputCheckbox.isChecked():
            if not self.data_loaded:
                self.data, self.data_filtered = [], []
                self.data_loaded = True

            pos = self.unitCirclePlot.getViewBox().mapSceneToView(pos)
            amp = np.sqrt(pos.x()**2 + pos.y()**2)

            self.mouse_signal_ptr += 1

            self.data = np.append(self.data, amp)
            filter_order = len(self.zero_pole_data["Zeros"]) + len(self.zero_pole_data["Poles"])
            if self.mouse_signal_ptr > filter_order:
                self.set_filtered_data(self.mouse_signal_ptr)

            self.mouseInputPlot.setRange(xRange=[max(0, len(self.data) - 200), len(self.data)])
            self.mouseFilteredOutput.setRange(xRange=[max(0, len(self.data) - 200), len(self.data)])




    def reset_viewport_range(self):
        for plot in [self.mouseInputPlot, self.mouseFilteredOutput]:
            plot.setRange(xRange=[0, 1000])

    

    def clear_points(self, point_type):
        if point_type in ["Zeros", "Poles"]:
            self.zero_pole_data[point_type].clear()
        else:
            for point_type in ["Zeros", "Poles"]:
                self.zero_pole_data[point_type].clear()

            self.data_filtered = self.data
        
        self.update_unit_circle_plot()

    
    def toggle_all_pass(self):
        self.update_allpass_plot()
        self.update_response_plots()


    def check_zero_radio_button(self):
        self.addZeroRadioButton.setChecked(True)

    def check_pole_radio_button(self):
        self.addPoleRadioButton.setChecked(True)


        
if __name__ == "__main__":
    app = QApplication([])
    window = DigitalFilterDesigner()
    app.exec_()