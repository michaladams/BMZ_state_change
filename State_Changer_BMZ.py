import sys
import os
import time
import datetime

import PyQt5
import canopen
import can
from can import Message, interfaces, Bus, interface

from PyQt5 import QtCore, QtGui
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QWidget, QPushButton, QMessageBox, \
    QMainWindow, QGraphicsScene, QLabel, QPlainTextEdit

# ################################################### Program workflow         ######################################
# 1. Execute Qt main window
# 2. Check Can converter connection:
#                 - QMessageBox with error information if connection failure - restart require
#                 - create files in data folder for present day log
# 3. If pushButton_connect_to_battery clicked:
#        - check for heartbeat(start heart_beat_control function :
#               - if present:
#               - if absent:
#                   -set
#               - if error:

# ################################################### load ui file          #######################################
uifile_1 = 'BMZ_state_changer.ui'
form_1, base_1 = uic.loadUiType(uifile_1)
# ################################################# Global variables       #######################################
can_converter_type = ""
bus = 0
actual_battery_state = 5
pilot_counter = 0
peak_pressent = 0
ixxata_pressent = 0
state_change_counter = 0       # this variable is used if CAN error appear - state change is repeat until this equal 3
# Start with creating a network representing one CAN bus
network = canopen.Network()
# Add some nodes with corresponding Object Dictionaries
network.add_node(4, 'od.eds')
node = network[4]
dir_path = os.path.dirname(os.path.realpath(__file__))
log_files_path = os.path.join(dir_path, "data/").replace("\\", "/")
# ##################################################  BEGINNING          #######################################

BMS_WAIT_HEARTBEAT_ON = 0
BMS_SEND_PASS_1_ON = 1
BMS_SEND_PASS_2_ON = 2

# ############################################      BMZ ADDRESSES        #######################################
BMS_tx_cobid = 0x604
BMS_rx_cobid = 0x584
BMS_heartbeat = 0x704

# ########################################## set python program directory path  #######################################

dir_path = os.path.dirname(os.path.realpath(__file__))

# ##########################################  BMZ passwords     ##########################################

BMZ_pass_1 = 0x77777777
BMZ_pass_2 = 0x77777777

# ###########################################    MAIN PROGRAM       ##################################################


class State_changer_mainWindow(base_1, form_1):

    global can_converter_type

    def __init__(self):
        try:
            # print("start of __init__ in main: \n------------------------------------------------ ")
            super(base_1, self).__init__()
            self.setupUi(self)
            # print(can_converter_type)
            self.create_log_file()           # creation of folder for day log file
            self.can_converter_control()
            # self.can_converter_reset()


            # - - - - - - - - - - - - - -  Connecting buttons   - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            self.pushButton_connect_to_battery.clicked.connect(self.pushButton_connect_to_battery_click)
            # self.pushButton_state_change_on_sleep.clicked.connect(self.change_from_active_to_sleep)
            # self.pushButton_state_change_on_active.clicked.connect(self.change_from_sleep_to_active)

            # print("End of __init__ in main\n------------------------------------------------ ")
        except Exception as e:
            print("---------------in State_changer_mainWindow __init__(self): " + str(e))
            
    def change_from_active_to_sleep(self):
        try:
            print("start of change_from_active_to_sleep \n------------------------------------------------ ")
            self.pushButton_state_change_on_sleep.setEnabled(False)
            self.pushButton_state_change_on_active.setEnabled(False)
            self.label_actual_state.setText(" ")
            try:
                # ---------------------   canopen module ----------------------------------------
                print(" - -- - - - - - -  State change(active -- > sleep) canopen module - - - - - - - - - - - - - - ")
                bus_change_from_active_to_sleep = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                # Transmit SYNC every 100 ms
                bus_change_from_active_to_sleep.sync.start(0.1)
                try:
                    node.sdo.download(0x3001, 1, b'\x77\x77\x77\x77')
                except Exception as e:
                    print("---------------password 1 sending error: " + str(e))
                print("SENDING password 2")
                try:
                    node.sdo.download(0x3001, 2, b'\x77\x77\x77\x77')
                except Exception as e:
                    print("---------------password 2 sending error: " + str(e))
                print("SENDING sleep bit....")
                try:
                    node.sdo.download(0x500b, 4, b'\x03')                           # write "sleep function bits"
                    print("Battery should be in sleep mode")
                    canopen_module_change_active_to_sleep_result = "change_OK"
                except Exception as e:
                    print("---------------sleep bit sending error: " + str(e))
                    canopen_module_change_active_to_sleep_result = "change_error"
                bus_change_from_active_to_sleep.sync.stop()
                bus_change_from_active_to_sleep.disconnect()        
            except Exception as e:
                print("---------------in state change(active -- > sleep) canopen module: " + str(e))
                canopen_module_change_active_to_sleep_result = "change_error"
            canopen_module_read_result_after_change = self.actual_battery_state_readed()
            print("change result from_canopen module - readed state: " + str(canopen_module_read_result_after_change))
            
            if canopen_module_change_active_to_sleep_result == "change_OK" and canopen_module_read_result_after_change == "SLEEP":
                self.plainTextEdit.setPlainText("Stan zmieniono na:")
                self.label_actual_state.setText(canopen_module_read_result_after_change)
                self.add_data_to_log_file("State change sleep-->active by canopen module" + " | " +
                                          "Readed state after change: " + canopen_module_read_result_after_change)
            if canopen_module_change_active_to_sleep_result == "change_error" or canopen_module_read_result_after_change != "SLEEP":
                print("There was a problem in canopen module. Other module to change initialization(can)")
                # ---------------------   can module ----------------------------------------
                print(" - -- - - - - - -  State change(active -- > sleep) can module - - - - - - - - - - - - - - ")
                try:         
                    bus_state_change_in_can = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                    can_module_change_active_to_sleep_result = " " 
                    print(" - -- - - - - - - - - - - - - - - PASS 1- -  - - - -  - - - -  - - - -  - - - - - - ")
                    try:
                        pass1_to_send = [0x23, 0x01, 0x30, 0x01, 0x77, 0x77, 0x77, 0x77]
                        msg_pass_1 = can.Message(arbitration_id=BMS_tx_cobid, data=pass1_to_send, is_extended_id=False, dlc=8)
                        bus_state_change_in_can.send(msg_pass_1)
                    except can.CanError:
                        print("Message NOT sent")
                    password1_ack = 0
                    while password1_ack < 5 :
                        try:      
                            pass1_control = bus_state_change_in_can.recv(0.2)
                            print("reciving message")
                            # print(pass1_control)
                            print(pass1_control.arbitration_id)
                            if pass1_control.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                                print("There is an answer ")
                                print(pass1_control)
                            time.sleep(0.1)    
                        except can.CanError:
                            print("in while for pass1 ack message reciving in can module")
                        password1_ack += 1
                    print(" - -- - - - - - - - - - - - - - - PASS 2- -  - - - -  - - - -  - - - -  - - - - - - ")
                    try:
                        pass2_to_send = [0x23, 0x01, 0x30, 0x02, 0x77, 0x77, 0x77, 0x77]
                        msg_pass_2 = can.Message(arbitration_id=BMS_tx_cobid, data=pass2_to_send, is_extended_id=False, dlc=8)
                        bus_state_change_in_can.send(msg_pass_2)
                    except can.CanError:
                        print("Message NOT sent")
                    password2_ack = 0
                    while password2_ack < 5 :
                        try:      
                            pass2_control = bus_state_change_in_can.recv(0.2)
                            print("reciving message")
                            # print(pass2_control)
                            print(pass2_control.arbitration_id)
                            if pass2_control.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                                print("There is an answer ")
                                print(pass2_control)
                            time.sleep(0.1)    
                        except can.CanError:
                            print("in while for pass2 ack message reciving in can module")
                        password2_ack += 1
                    print(" - -- - - - - - - - - - - - - - - change state - -  - - - -  - - - -  - - - -  - - - - - - ")
                    try:
                        change_state_to_send = [0x23, 0x0b, 0x50, 0x04, 0x03, 0x0, 0x0, 0x0]
                        msg_change_state = can.Message(arbitration_id=BMS_tx_cobid, data=change_state_to_send, is_extended_id=False, dlc=8)
                        bus_state_change_in_can.send(msg_change_state)
                    except can.CanError:
                        print("Message NOT sent")
                        can_module_change_active_to_sleep_result = "change_error"
                    can_module_change_ack = 0
                    while can_module_change_ack < 5 :
                        state_can_control = bus_state_change_in_can.recv(0.2)
                        print("reciving message")
                        if state_can_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584: ")
                            print(state_can_control)
                            can_module_change_active_to_sleep_result = "change_OK"
                        can_module_change_ack += 1
                    print("Battery should be in sleep mode now")   
                    bus_state_change_in_can.shutdown()
                    can_module_change_result = self.actual_battery_state_readed()
                    print("change result from_can module - readed state: " + str(can_module_change_result))
                    if can_module_change_active_to_sleep_result == "change_OK" and can_module_change_result == "SLEEP":
                        self.plainTextEdit.setPlainText("Stan zmieniono na:")
                        self.label_actual_state.setText(can_module_change_result)
                        self.add_data_to_log_file("State change active-->sleep by can module" + " | " +
                                                  "Readed state after change: " + can_module_change_result)
                    if can_module_change_active_to_sleep_result == "change_error" or can_module_change_result == "ACTIVE":
                        self.label_actual_state.setText("ERROR")
                        self.add_data_to_log_file("State change active-->sleep by can module" + " | " +
                                                  "Readed state after change: " + can_module_change_result + " | "
                                                  + "ERROR")
                except Exception as e:
                    print("---------------in state change(active -- > sleep) can module: " + str(e))
            
        except Exception as e:
            print("---------------in change_from_active_to_sleep:  " + str(e))
            self.unexpected_error__Qmessage()
            self.label_actual_state.setText("ERROR")
            
    def change_from_sleep_to_active(self):
        try:
            print("start of change_from_sleep_to_active \n------------------------------------------------ ")
            self.pushButton_state_change_on_sleep.setEnabled(False)
            self.pushButton_state_change_on_active.setEnabled(False)
            self.label_actual_state.setText(" ")
            canopen_module_change_sleep_to_active_result = ""
            try:
                # ---------------------   canopen module ----------------------------------------
                print(" - -- - - - - - -  State change(sleep -- > active) canopen module - - - - - - - - - - - - - - ")
                bus_change_from_sleep_to_active = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                # Transmit SYNC every 100 ms
                bus_change_from_sleep_to_active.sync.start(0.1)
                print("SENDING password 1")
                try:
                    node.sdo.download(0x3001, 1, b'\x77\x77\x77\x77')
                except Exception as e:
                    print("---------------password 1 sending error: " + str(e))
                print("SENDING password 2")
                try:
                    node.sdo.download(0x3001, 2, b'\x77\x77\x77\x77')
                except Exception as e:
                    print("---------------password 2 sending error: " + str(e))
                print("SENDING sleep bit....")
                try:
                    node.sdo.download(0x500b, 4, b'\x02')                           # write "active function bits"
                    print("Battery should be in active mode")
                    canopen_module_change_sleep_to_active_result = "change_OK"
                except Exception as e:
                    print("---------------sleep bit sending error: " + str(e))
                    canopen_module_change_sleep_to_active_result = "change_error"
                bus_change_from_sleep_to_active.sync.stop()
                bus_change_from_sleep_to_active.disconnect()          
            except Exception as e:
                print("---------------in state change(sleep-- > active) canopen module: " + str(e))
                canopen_module_change_sleep_to_active_result = "change_error"
            canopen_module_change_result_to_active = self.actual_battery_state_readed()
            print("change result from_canopen module - readed state: " + str(canopen_module_change_result_to_active))
            if canopen_module_change_sleep_to_active_result == "change_OK" and canopen_module_change_result_to_active == "ACTIVE":
                self.plainTextEdit.setPlainText("Stan zmieniono na:")
                self.label_actual_state.setText(canopen_module_change_result_to_active)
                self.add_data_to_log_file("State change sleep-->active by canopen module" + " | " +
                                          "Readed state after change: " + canopen_module_change_result_to_active)
            if canopen_module_change_sleep_to_active_result == "change_error" or canopen_module_change_result_to_active != "ACTIVE":
                print("There was a problem in canopen module. Other module to change initialization(can)")
                # ---------------------   can module ----------------------------------------
                print(" - -- - - - - - -  State change(sleep -- > active) can module - - - - - - - - - - - - - - ")
                try:         
                    bus_state_change_in_can = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                    can_module_change_sleep_to_active_result = " " 
                    print(" - -- - - - - - - - - - - - - - - PASS 1- -  - - - -  - - - -  - - - -  - - - - - - ")
                    try:
                        pass1_to_send = [0x23, 0x01, 0x30, 0x01, 0x77, 0x77, 0x77, 0x77]
                        msg_pass_1 = can.Message(arbitration_id=BMS_tx_cobid, data=pass1_to_send, is_extended_id=False, dlc=8)
                        bus_state_change_in_can.send(msg_pass_1)
                    except can.CanError:
                        print("Message NOT sent")
                    password1_ack = 0
                    while password1_ack < 5 :
                        try:      
                            pass1_control = bus_state_change_in_can.recv(0.2)
                            print("reciving message")
                            # print(pass1_control)
                            print(pass1_control.arbitration_id)
                            if pass1_control.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                                print("There is an answer ")
                                print(pass1_control)
                            time.sleep(0.1)    
                        except can.CanError:
                            print("in while for pass1 ack message reciving in can module")
                        password1_ack += 1
                    print(" - -- - - - - - - - - - - - - - - PASS 2- -  - - - -  - - - -  - - - -  - - - - - - ")
                    try:
                        pass2_to_send = [0x23, 0x01, 0x30, 0x02, 0x77, 0x77, 0x77, 0x77]
                        msg_pass_2 = can.Message(arbitration_id=BMS_tx_cobid, data=pass2_to_send, is_extended_id=False, dlc=8)
                        bus_state_change_in_can.send(msg_pass_2)
                    except can.CanError:
                        print("Message NOT sent")
                    password2_ack = 0
                    while password2_ack < 5 :
                        try:      
                            pass2_control = bus_state_change_in_can.recv(0.2)
                            print("reciving message")
                            # print(pass2_control)
                            print(pass2_control.arbitration_id)
                            if pass2_control.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                                print("There is an answer ")
                                print(pass2_control)
                            time.sleep(0.1)    
                        except can.CanError:
                            print("in while for pass2 ack message reciving in can module")
                        password2_ack += 1
                    print(" - -- - - - - - - - - - - - - - - change state - -  - - - -  - - - -  - - - -  - - - - - - ")
                    try:
                        change_state_to_send = [0x23, 0x0b, 0x50, 0x04, 0x02, 0x0, 0x0, 0x0]
                        msg_change_state = can.Message(arbitration_id=BMS_tx_cobid, data=change_state_to_send, is_extended_id=False, dlc=8)
                        bus_state_change_in_can.send(msg_change_state)
                    except can.CanError:
                        print("Message NOT sent")
                        can_module_change_sleep_to_active_result = "change_error"
                    can_module_change_ack = 0
                    while can_module_change_ack < 5 :
                        state_can_control = bus_state_change_in_can.recv(0.2)
                        print("reciving message")
                        if state_can_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584: ")
                            print(state_can_control)
                            can_module_change_sleep_to_active_result = "change_OK"
                        can_module_change_ack += 1
                    print("Battery should be in active mode now")   
                    bus_state_change_in_can.shutdown()
                    can_module_result_in_sleep_to_active = self.actual_battery_state_readed()
                    print("change result from_can module - readed state: " + str(can_module_change_result))
                    if can_module_change_sleep_to_active_result == "change_OK" and can_module_change_result == "ACTIVE":
                        self.plainTextEdit.setPlainText("Stan zmieniono na:")
                        self.label_actual_state.setText(can_module_result_in_sleep_to_active)
                        self.add_data_to_log_file("State change sleep-->active by can module" + " | " +
                                                  "Readed state after change: " + can_module_result_in_sleep_to_active)
                    if can_module_change_sleep_to_active_result == "change_error" or can_module_change_result == "SLEEP":
                        self.label_actual_state.setText("ERROR")
                        self.add_data_to_log_file("State change active-->sleep by can module" + " | " +
                                                  "Readed state after change: " + can_module_change_result + " | " + " | " + "ERROR")
                except Exception as e:
                    print("---------------in state change(sleep-- > active) can module: " + str(e))
                    
        except Exception as e:
            print("---------------in change_from_sleep_to_active:  " + str(e))
            self.unexpected_error__Qmessage()
            
    def pushButton_connect_to_battery_click(self):
        print("start of pushButton_connect_to_battery_click \n------------------------------------------------ ")
        try:
            # print(can_converter_type)
            time.sleep(1)
            self.pushButton_state_change_on_sleep.setEnabled(False)
            self.pushButton_state_change_on_active.setEnabled(False)
            self.baterry_heartbeat_control_progress.setValue(0)
            self.battery_state_control_progress.setValue(0)
            self.plainTextEdit.setPlainText("Bateria jest w stanie:")
            self.label_actual_state.setText(" ")
            self.label_actual_serial_number.setText(" ")
            battery_heartbeat = ""
            battery_heartbeat = self.heart_beat_control()
            
            print("Heartbeat result:")
            print(battery_heartbeat)
            if battery_heartbeat == "heartbeat Ok":
                print('Beginning of pilot control')
                battery_pilot = self.pilot_control()
                print("Pilot control result:")
                print(battery_pilot)
                if battery_pilot == "pilot OK":
                    print("Pilot control pass. Begin of control serial number ")
                    battery_SN = self.read_battery_serial_number()
                    if battery_SN == "ERROR":
                        print("Can't read serial number")
                        self.SN_error__Qmessage()
                        
                    if battery_SN != "ERROR":
                        print("Serial number readed correctly:")
                        print(battery_SN)
                    self.label_actual_serial_number.setText(battery_SN)
                    actual_battery_state_in_click = ""
                    actual_battery_state_in_click = self.actual_battery_state_readed()
                    print("Actual battery state:")
                    print(actual_battery_state_in_click)
                    if actual_battery_state_in_click == "ACTIVE":
                        self.label_actual_state.setText("ACTIVE")
                        self.pushButton_state_change_on_sleep.setEnabled(True)
                    if actual_battery_state_in_click == "SLEEP":
                        self.label_actual_state.setText("SLEEP")
                        self.pushButton_state_change_on_active.setEnabled(True)
                    if actual_battery_state_in_click == "READ STATE ERROR":
                        self.label_actual_state.setText("ERROR")
                    self.add_data_to_log_file("SN: " + str(battery_SN) + " | " + "Readed state: " +
                                              str(actual_battery_state_in_click))
                if battery_pilot == "No pilot":
                    print("Pilot control fail.")
                    self.pilot_Qmessage()
            if battery_heartbeat == "NO heartbeat":
                # print('There is no heartbeata')
                self.heartbeat_Qmessage()
            
        except Exception as e:
            print("in pushButton_connect_to_battery_click: " + str(e))
            
    def actual_battery_state_readed(self):
        try:
            print("start of actual_battery_state_readed \n------------------------------------------------ ")
            # ---------------------   canopen module ----------------------------------------
            counter_state_temp_canopen_module = 0
            state_in_canopen_module = " " 
            try:
                bus_actual_state = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                # Transmit SYNC every 200 ms
                bus_actual_state.sync.start(0.2)
                while counter_state_temp_canopen_module < 1:
                    try:
                        device_type_data = node.sdo.upload(0x500b, 4)  # check actual state object
                        
                    except Exception as e:
                        print("in actual_battery_state_readed in canopen module. upload 500b,4 " + str(e))
                    if device_type_data == b'\x02':                 # 2 if battery is in ACTIVE mode
                        print('Is active')
                        state_in_canopen_module = "ACTIVE"
                        return "ACTIVE"
                    if device_type_data == b'\x03':                 # 3 if battery is in SLEEP mode
                        print('Is sleep')
                        state_in_canopen_module = "SLEEP"
                        return "SLEEP"
                    if device_type_data != b'\x03' and device_type_data != b'\x02':
                        print('CAN\'T READ')
                        state_in_canopen_module = "canopem module read state error"
                    counter_state_temp_canopen_module += 1
                    time.sleep(0.1)
                bus_actual_state.sync.stop()
                bus_actual_state.disconnect()
            except Exception as e:
                print("in actual_battery_state_readed in canopen module: " + str(e))
                
            print(state_in_canopen_module)
            if state_in_canopen_module == "canopem module read state error":
                # ---------------------   can module ----------------------------------------
                print(" - -- - - - - - - -  State of battery from can module - - - - - - - - - - - - - - - - - ")
                state_in_can_module = ""
                try:
                    bus_state_in_can = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                    to_send_for_state_in_can = [0x40, 0x0b, 0x50, 0x04, 0x0, 0x0, 0x0, 0x0]
                    msg_state_can_module = can.Message(arbitration_id=BMS_tx_cobid, data=to_send_for_state_in_can, is_extended_id=False, dlc=8)
                    try:
                        bus_state_in_can.send(msg_state_can_module)
                        # print("Message sent ok {}".format(bus_state_in_can.channel_info))
                        # print("data sent : " + str(to_send_for_state_in_can))
                    except can.CanError:
                        print("Message NOT sent in can module of actual_battery_state_readed")
                    temp_counter_can_state = 0
                    while temp_counter_can_state < 5 :
                        try:    
                            state_control_can_module = bus_state_in_can.recv(0.2)
                            print("recived message")
                            print(state_control_can_module)
                            if state_control_can_module.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                                print("There is an answer ")
                                print(state_control_can_module.data)
                                if state_control_can_module.data[4] == 2:
                                    print('Is active')
                                    state_in_can_module  = "ACTIVE"
                                    return "ACTIVE"
                                if state_control_can_module.data[4] == 3:
                                    print("Is sleep")
                                    state_in_can_module = "SLEEP"
                                    return "ACTIVE"                          
                            time.sleep(0.1) 
                        except can.CanError:
                            print("in while for maessage recive in can module")
                            return "READ STATE ERROR"
                        temp_counter_can_state += 1  
                    bus_state_in_can.shutdown()
                except can.CanError:
                    print("in actual_battery_state_readed in can module:")
        except Exception as e:
            print("in actual_battery_state_readed: " + str(e))
            return "READ STATE ERROR"
        
    def create_log_file(self):
        try:
            # print("start of create_log_file \n------------------------------------------------ ")
            os.chdir(log_files_path)  # set configuration file patch for os module
            today_date = datetime.datetime.now()
            name = str(today_date.date())
            # print(today_date)
            # print(name)
            try:
                file = open(name, 'a')  # Trying to create a new file or open one
                file.close()
            except Exception as e:
                print("Something went wrong!" + str(e))
            os.chdir(dir_path)  # set python file patch for os module
            # print("End of create_log_file \n------------------------------------------------ ")
        except Exception as e:
            print("in create_log_file: " + str(e))

    def add_data_to_log_file(self, data_to_append):
        try:
            # print("start of add_data_to_log_file \n------------------------------------------------ ")
            os.chdir(log_files_path)  # set configuration file patch for os module
            today_date = datetime.datetime.now()
            name_of_file = str(today_date.date())
            # print(name_of_file)
            file = open(name_of_file, 'a+')  # Trying to create a new file or open one
            file.write(str(today_date) + " | " + data_to_append + "\n")
            file.close()
            os.chdir(dir_path)  # set python file patch for os module
            # print("End of add_data_to_log_file \n------------------------------------------------ ")
        except Exception as e:
            print("in add_data_to_log_file: " + str(e))

    def read_battery_serial_number(self):
        try:
            # print("start of read_battery_serial_number \n------------------------------------------------ ")
            print(" - -- - - - - - - -  State of battery from canopen module - - - - - - - - - - - - - - - - - ")
            bus_serial_read = network.connect(bustype='ixxat', channel=0, bitrate=500000)
            battery_serial_number = " "
            counter_state_temp_canopen_module = 0
            # Transmit SYNC every 200 ms
            network.sync.start(0.2)
            while counter_state_temp_canopen_module < 2:
                # print(counter_state_temp_canopen_module)
                # print("Here is battery SN")
                try:
                    device_SN_1 = node.sdo.upload(0x6030, 1)  # check actual SN
                    # print(str(device_SN_1, 'utf-8'))
                except Exception as e:
                    print("in read_battery_serial_number canopen module, upload device_SN_1 fail: " + str(e))
                    device_SN_1 = "XXX"
                try:
                    device_SN_2 = node.sdo.upload(0x6030, 2)  # check actual state object
                    # print(str(device_SN_2, 'utf-8'))
                except Exception as e:
                    print("in read_battery_serial_number canopen module, upload device_SN_1 fail: " + str(e))
                    device_SN_2 = "XXX"
                try:
                    device_SN_3 = node.sdo.upload(0x6030, 3)  # check actual state object
                    # print(str(device_SN_3, 'utf-8'))
                except Exception as e:
                    print("in read_battery_serial_number canopen module, upload device_SN_1 fail: " + str(e))
                    device_SN_3 = "XXX"
                # if any device_SN error accure, "XXX" will be set. Below line will reply error because "XXX" can't be decoding with 'utf-8'
                battery_serial_number = (str(device_SN_1, 'utf-8') + str(device_SN_2, 'utf-8')
                                         + str(device_SN_3, 'utf-8'))   
                # print(battery_serial_number)
                time.sleep(0.1)
                counter_state_temp_canopen_module += 1
            bus_serial_read.sync.stop()
            bus_serial_read.disconnect()
            return battery_serial_number
            # print("End of read_battery_serial_number \n------------------------------------------------ ")
        except Exception as e:
            print("in read_battery_serial_number: " + str(e))
            return "ERROR"
        
    def pilot_control(self):
        try:
            print("start of pilot_control \n------------------------------------------------ ")
            try:
                pilot_counter_in_canopen_module = 0
                # ---------------------   canopen module ----------------------------------------
                print("- -- - - - - - - -  pilot control in canopen module")
                bus_pilot_control_canopen = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                counter_temp = 0
                # Transmit SYNC every 200 ms
                bus_pilot_control_canopen.sync.start(0.2)
                device_type_data = b'\x00'
                while counter_temp < 5:
                    try:
                        device_type_data = node.sdo.upload(0x4001, 6)
                    except Exception as e:
                        print("in pilot_control canopen module, upload fail: " + str(e))
                    time.sleep(0.1)
                    if device_type_data == b'\x01':
                        pilot_counter_in_canopen_module += 1
                        # print("pilot counter in canopen module " + str(pilot_counter_in_canopen_module))
                    # print("progress counter " + str(counter_temp))
                    counter_temp += 1

                    self.battery_state_control_progress.setValue(int(counter_temp))
                bus_pilot_control_canopen.sync.stop()
                bus_pilot_control_canopen.disconnect()
                print("Pilot count in canopen module:")
                print(pilot_counter_in_canopen_module)
                counter_temp = 0

            except Exception as e:
                print("in pilot_control canopen module: " + str(e))
                pilot_counter_in_canopen_module = 0
            # ----------------------------------------------------------------------------------
            # -----------------------   can module ----------------------------------------
            try:
                print(" - -- - - - - - - -  pilot control in can module - second check")
                bus_pilot_control_can = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                # data sent in SDO to Read Dictionary Object
                # [Byte 0       ,Byte 1, Byte 2,Byte 3,	    Byte 4,	Byte 5,	Byte 6,	Byte 7]
                # [Command Code ,Index,         Sub Index	Data]
                # index is reversed
                # to_send = [64, 1, 64, 6, 0, 0, 0, 0]
                to_send_for_pilot = [0x40, 0x01, 0x40, 0x06, 0x0, 0x0, 0x0, 0x0]
                msg_pilot_can_module = can.Message(arbitration_id=BMS_tx_cobid, data=to_send_for_pilot, is_extended_id=False, dlc=8)
                pilot_counter_in_can_module = 0
                counter_temp_for_pilot_can_module = 5

                while counter_temp_for_pilot_can_module < 10:                     # send 5 times message to get answer 5 times (start count from 5 to 10 for progress)
                    print("Start while")                                                                  # (pilot signal change even if pilot is connected)
                    try:
                        bus_pilot_control_can.send(msg_pilot_can_module)
                        # print("Message sent ok {}".format(bus_pilot_control_can.channel_info))
                        # print("data sent : " + str(to_send_for_pilot))
                    except can.CanError:
                        print("Message NOT sent")
                    x = 0
                    while x < 5 :
                        try:
                                  
                            pilot_control = bus_pilot_control_can.recv(0.2)
                            print("recived message")
                            print(pilot_control)
                            # print(pilot_control.arbitration_id)
                            if pilot_control.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                                print("There is an answer ")
                                print(pilot_control.data)
                                # print(pilot_control.data[4])                # get value from bytearray- this byte have 0 or 1
                                if pilot_control.data[4] != 0:
                                    pilot_counter_in_can_module += 1
                                print(pilot_counter_in_can_module)
                            # print(pilot_control)
                            time.sleep(0.1)
                            
                        except can.CanError:
                            print("in while for maessage recive in can module")
                        x += 1
                    counter_temp_for_pilot_can_module += 1
                    print(counter_temp_for_pilot_can_module)
                    self.battery_state_control_progress.setValue(int(counter_temp_for_pilot_can_module))
                    x = 0
                bus_pilot_control_can.shutdown()
                print("Pilot in can module:")
                print(pilot_counter_in_can_module)    
            except Exception as e:
                print("in pilot_control can module: " + str(e))
                pilot_counter_in_can_module = 0
            print("heartbeats:")
            print("in canopen module, in can module")
            print(pilot_counter_in_canopen_module, pilot_counter_in_can_module)
            
            if pilot_counter_in_canopen_module != 0 or pilot_counter_in_can_module != 0:
                print("Pilot found in modules!!!" + "CanOpen: " + str(pilot_counter_in_canopen_module) + " Can: " + str(pilot_counter_in_can_module))
                return "pilot OK"
            else:
                # print("No pilot in modules")
                return "No pilot"
        except Exception as e:
            print("in pilot_control: " + str(e))
            return "No pilot"

    def heart_beat_control(self):
        
            # print("start of heart_beat_control \n------------------------------------------------ ")
            canopen_control_needed = ""
            # -----------------------   can module ------------------------------------------------

            try:
                heart_beat_counter = 0
                print("start heart_beat_control by can module")
                try:
                    bus_can_module_heartbeat = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                    counter_for_heartbeat_control = 1
                    
                    while counter_for_heartbeat_control < 5:
                        # print(counter_for_heartbeat_control)
                        heart_beat_control = bus_can_module_heartbeat.recv(2)               # waiting 2 s for recive message
                        print(heart_beat_control)
                        # print(heart_beat_control.data)
                        if heart_beat_control.arbitration_id == 1796:
                            print("heartbeat Ok ")
                            heart_beat_counter += 1
                        if heart_beat_control is None:
                            print("NO heartbeat")
                        if heart_beat_control.arbitration_id != 1796:
                            print("I found frames from battery but there is no heartbeat frame")
                        time.sleep(0.1)
                        counter_for_heartbeat_control += 1
                        self.baterry_heartbeat_control_progress.setValue(int(2*counter_for_heartbeat_control))
                    print("heartbeat counter:")
                    print(heart_beat_counter)
                    bus_can_module_heartbeat.shutdown()
                except Exception as e:
                    print("in can module of heart_beat_control: " + str(e))
                if heart_beat_counter != 0:
                    # print("heartbeat Ok in can module")   
                    return "heartbeat Ok"        
                if heart_beat_counter == 0:
                    print("NO heartbeat in can module")
                # ---------------------   canopen module ----------------------------------------
                    try:
                        canopen_module_heart_answer = ""
                        print(" start heartbeat control by canopen module")
                        bus_canopen_module_heartbeat = network.connect(bustype='ixxat', channel=0, bitrate=500000)

                        # print(bus_canmodule_heartbeat)
                        counter_temp = 0
                        # Transmit SYNC every 100 ms
                        bus_canopen_module_heartbeat.sync.start(0.1)
                        while counter_temp < 5:
                            try:
                                bus_canopen_module_heartbeat.send_message(0x0, [0x1, 0])
                                print("waiting for heartbeat ")
                                canopen_module_heart_answer = node.nmt.wait_for_heartbeat(timeout=2)
                            except Exception as e:
                                print("in canopen module of heart_beat_control1: " + str(e))
                            counter_temp += 1
                            temp_for_progress_bar = 2 * counter_temp
                            print(canopen_module_heart_answer)
                            self.baterry_heartbeat_control_progress.setValue(int(temp_for_progress_bar))                      
                        bus_canopen_module_heartbeat.sync.stop()
                        bus_canopen_module_heartbeat.disconnect()
                        
                        if canopen_module_heart_answer == "OPERATIONAL":
                            return "heartbeat Ok"
                        if canopen_module_heart_answer != "OPERATIONAL":
                            return "NO heartbeat"
                    except Exception as e:
                        print("in canopen module of heart_beat_control2: " + str(e))
                        return "NO heartbeat"
                        
            except Exception as e:
                print("in heart_beat_control: " + str(e))

    def can_converter_control(self):
        try:
            # print("start of can_converter_control \n------------------------------------------------ ")
            
            global can_converter_type

            converter_control = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
            # print(bus)
            converter_control.shutdown()
            can_converter_type = "ixxata"
            # print(can_converter_type)

            # print("End of can_converter_control\n------------------------------------------------ ")
        except Exception as et:
            print("in can_converter_control: " + str(et))
            print("No CAN converted connect ")
            self.pushButton_connect_to_battery.setEnabled(False)
            self.CAN_Qmessage()
            can_converter_type = "no connect"

# ###################################################################################################################
# ###################################################################################################################
# #####################################     Battery connect checking       ##########################################

    def pilot_Qmessage(self):
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Wykryto połączenie z baterią ale nie wykryto sygnału pilota. \n"
                        "Sprawdz poziom małej baterii (9V) na końcówce przewodu.\n"
                        "Wykonanie operacji zmiany stanu bez sygnału pilota\n"
                        "nie jest dopuszczale przez BMZ.\n"
                        "W przypadku wielokrotnego powtórzenia błędu, zresetuj aplikację")

            msg.setWindowTitle("Pilot error")

            msg.setStyleSheet("QPushButton"
                              "{"
                              "background-color:transparent; text-align: center; "
                              "vertical-align: middle; padding: 5px 25px; border: 3px solid #3f677e;"
                              "border-radius: 12px; background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299,y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245)); "
                              "font: normal normal bold 80% arial;color: #ffffff;"
                              "}"
                              "QPushButton:hover"
                              "{"
                              "background-color:transparent; text-align: center;"
                              "vertical-align: middle; padding: 5px 5px; border: 3px solid #65a5ca;"
                              "border-radius: 12px;background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299, y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245));"
                              "font: normal normal bold 80% arial; color: #ffffff;text-decoration: none;"
                              "}"
                              "QPushButton:pressed"
                              "{"
                              "background-color: qlineargradient(spread:pad, x1:0.503, y1:0.284091, x2:0.503299, "
                              "y2:0.887, stop:0 rgba(14,38,53, 255), stop:1 rgba(76,128,156,245));"
                              "}"
                              "QLabel{color:black;}"
                              "QMessageBox"
                              "{"
                              "background-color: rgb(136,176,221);"
                              "}")
            msg.exec()
           
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))

# #####################################     Heartbeat checking       ##########################################

    def heartbeat_Qmessage(self):
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Nie wykryto połączenia z baterią. Sprawdz połaczenie i spróbuj ponownie. \n")

            msg.setWindowTitle("Connection error")

            msg.setStyleSheet("QPushButton"
                              "{"
                              "background-color:transparent; text-align: center; "
                              "vertical-align: middle; padding: 5px 25px; border: 3px solid #3f677e;"
                              "border-radius: 12px; background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299,y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245)); "
                              "font: normal normal bold 80% arial;color: #ffffff;"
                              "}"
                              "QPushButton:hover"
                              "{"
                              "background-color:transparent; text-align: center;"
                              "vertical-align: middle; padding: 5px 5px; border: 3px solid #65a5ca;"
                              "border-radius: 12px;background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299, y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245));"
                              "font: normal normal bold 80% arial; color: #ffffff;text-decoration: none;"
                              "}"
                              "QPushButton:pressed"
                              "{"
                              "background-color: qlineargradient(spread:pad, x1:0.503, y1:0.284091, x2:0.503299, "
                              "y2:0.887, stop:0 rgba(14,38,53, 255), stop:1 rgba(76,128,156,245));"
                              "}"
                              "QLabel{color:black;}"
                              "QMessageBox"
                              "{"
                              "background-color: rgb(136,176,221);"
                              "}")

            msg.exec()
          
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))
# #####################################     Can checking       #############################################

    def CAN_Qmessage(self):
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Nie wykryto połączenia z konwerterem CAN.\n Sprawdz połaczenie i uruchom program ponownie")

            msg.setWindowTitle("CAN error")

            msg.setStyleSheet("QPushButton"
                              "{"
                              "background-color:transparent; text-align: center; "
                              "vertical-align: middle; padding: 5px 25px; border: 3px solid #3f677e;"
                              "border-radius: 12px; background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299,y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245)); "
                              "font: normal normal bold 80% arial;color: #ffffff;"
                              "}"
                              "QPushButton:hover"
                              "{"
                              "background-color:transparent; text-align: center;"
                              "vertical-align: middle; padding: 5px 5px; border: 3px solid #65a5ca;"
                              "border-radius: 12px;background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299, y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245));"
                              "font: normal normal bold 80% arial; color: #ffffff;text-decoration: none;"
                              "}"
                              "QPushButton:pressed"
                              "{"
                              "background-color: qlineargradient(spread:pad, x1:0.503, y1:0.284091, x2:0.503299, "
                              "y2:0.887, stop:0 rgba(14,38,53, 255), stop:1 rgba(76,128,156,245));"
                              "}"
                              "QLabel{color:black;}"
                              "QMessageBox"
                              "{"
                              "background-color: rgb(136,176,221);"
                              "}")
            msg.exec()
           
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))

# ###################################################################################################################
    # #####################################     Log_error__Qmessage       ########################################
    def SN_error__Qmessage(self):
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Nie można odczytać numeru seryjnego baterii.\nLog zostanie utworzony bez numeru\n"
                        "Zalecane powtórzenie próby połączenia")

            msg.setWindowTitle("Serial number error")

            msg.setStyleSheet("QPushButton"
                              "{"
                              "background-color:transparent; text-align: center; "
                              "vertical-align: middle; padding: 5px 25px; border: 3px solid #3f677e;"
                              "border-radius: 12px; background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299,y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245)); "
                              "font: normal normal bold 80% arial;color: #ffffff;"
                              "}"
                              "QPushButton:hover"
                              "{"
                              "background-color:transparent; text-align: center;"
                              "vertical-align: middle; padding: 5px 5px; border: 3px solid #65a5ca;"
                              "border-radius: 12px;background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299, y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245));"
                              "font: normal normal bold 80% arial; color: #ffffff;text-decoration: none;"
                              "}"
                              "QPushButton:pressed"
                              "{"
                              "background-color: qlineargradient(spread:pad, x1:0.503, y1:0.284091, x2:0.503299, "
                              "y2:0.887, stop:0 rgba(14,38,53, 255), stop:1 rgba(76,128,156,245));"
                              "}"
                              "QLabel{color:black;}"
                              "QMessageBox"
                              "{"
                              "background-color: rgb(136,176,221);"
                              "}")
            msg.exec()
            
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))

# #####################################     unexpected_error__Qmessage       ########################################

    def unexpected_error__Qmessage(self):
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Wystąpił nieoczekiwany błąd.\n Operacja przerwana.\nZalecany reset aplikacji")

            msg.setWindowTitle("Nieokreślony błąd")

            msg.setStyleSheet("QPushButton"
                              "{"
                              "background-color:transparent; text-align: center; "
                              "vertical-align: middle; padding: 5px 25px; border: 3px solid #3f677e;"
                              "border-radius: 12px; background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299,y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245)); "
                              "font: normal normal bold 80% arial;color: #ffffff;"
                              "}"
                              "QPushButton:hover"
                              "{"
                              "background-color:transparent; text-align: center;"
                              "vertical-align: middle; padding: 5px 5px; border: 3px solid #65a5ca;"
                              "border-radius: 12px;background-color:qlineargradient(spread:pad, x1:0.503, y1:0.284091,"
                              "x2:0.503299, y2:0.887, stop:0 rgba(23,64,89, 255), stop:1 rgba(76,128,156,245));"
                              "font: normal normal bold 80% arial; color: #ffffff;text-decoration: none;"
                              "}"
                              "QPushButton:pressed"
                              "{"
                              "background-color: qlineargradient(spread:pad, x1:0.503, y1:0.284091, x2:0.503299, "
                              "y2:0.887, stop:0 rgba(14,38,53, 255), stop:1 rgba(76,128,156,245));"
                              "}"
                              "QLabel{color:black;}"
                              "QMessageBox"
                              "{"
                              "background-color: rgb(136,176,221);"
                              "}")
            msg.exec()
        
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))


if __name__ == '__main__':

    app = QApplication(sys.argv)
    ex = State_changer_mainWindow()
    ex.show()
    sys.exit(app.exec_())
# ###################################################################################################################
