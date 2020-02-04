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
            self.pushButton_state_change_on_sleep.clicked.connect(self.change_from_active_to_sleep)
            self.pushButton_state_change_on_active.clicked.connect(self.change_from_sleep_to_active)

            # print("End of __init__ in main\n------------------------------------------------ ")
        except Exception as e:
            print("---------------in State_changer_mainWindow __init__(self): " + str(e))

    def change_from_active_to_sleep(self):
        try:
            # print("start of change_from_active_to_sleep \n------------------------------------------------ ")
            self.pushButton_state_change_on_sleep.setEnabled(False)
            self.pushButton_state_change_on_active.setEnabled(False)
            self.label_actual_state.setText(" ")
            canopen_module_change_active_to_sleep_result = ""
            canopen_module_change_result = ""
            # ---------------------   canopen module ----------------------------------------
            try:
                print(" - -- - - - - - -  State change(active -- > sleep) canopen module - - - - - - - - - - - - - - ")
                bus__active_to_sleep_canopen = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                # Transmit SYNC every 100 ms
                bus__active_to_sleep_canopen.sync.start(0.1)

                print("SENDING password 1")
                node.sdo.download(0x3001, 1, b'\x77\x77\x77\x77')
                print("SENDING password 2")
                node.sdo.download(0x3001, 2, b'\x77\x77\x77\x77')
                # print("SENDING disable awake/sleep time")
                # node.sdo.download(0x500b, 1, b'\x00')               # write 0 to disable awake/sleep time
                print("SENDING sleep bit....")
                node.sdo.download(0x500b, 4, b'\x03')               # write "sleep function bits" to sleep
                print("Battery should be in sleep mode")
                bus__active_to_sleep_canopen.sync.stop()
                bus__active_to_sleep_canopen.disconnect()
                canopen_module_change_active_to_sleep_result = "change_OK"
                canopen_module_change_result = self.actual_battery_state_readed()
                print("change result from_canopen module: " + str(canopen_module_change_result))
            except Exception as e:
                print("---------------in state change(active -- > sleep) canopen module: " + str(e))
                canopen_module_change_active_to_sleep_result = "change_error"

            print(canopen_module_change_active_to_sleep_result)
            print(canopen_module_change_result)
            if canopen_module_change_active_to_sleep_result == "change_OK" and canopen_module_change_result == "SLEEP":
                self.plainTextEdit.setPlainText("Stan zmieniono na:")
                self.label_actual_state.setText(canopen_module_change_result)
                self.add_data_to_log_file("State change active-->sleep by canopen module" + " | " +
                                          "Readed state after change: " + canopen_module_change_result)
            if canopen_module_change_active_to_sleep_result == "change_error" or \
                    canopen_module_change_result != "SLEEP":
                try:
                    print("There was a problem in canopen module. Other module to change initialization(can)")
                    # ---------------------   can module ----------------------------------------
                    print(" - -- - - - - - -  State change(active -- > sleep) can module - - - - - - - - - - - - - - ")
                    print(" - -- - - - - - - - - - - - - - - PASS 1- -  - - - -  - - - -  - - - -  - - - - - - ")
                    bus = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                    pass1_to_send = [0x23, 0x01, 0x30, 0x01, 0x77, 0x77, 0x77, 0x77]
                    msg1 = can.Message(arbitration_id=BMS_tx_cobid, data=pass1_to_send, is_extended_id=False, dlc=8)
                    bus.send(msg1)
                    print("Sending message:")
                    print(msg1)
                    counter_pass1_temp = 0
                    while counter_pass1_temp < 10:  # send 5 times message to get answer 5 times
                        # (pilot signal change even if pilot is connected)
                        try:
                            print("Waiting for ACK and others respond")
                            # print("Message sent ok {}".format(bus.channel_info))
                            # print("data sent : " + str(pass1_to_send))
                        except can.CanError:
                            print("Message NOT sent")
                        pass1_control = bus.recv(0.25)
                        # print("CAN responds:")
                        # print(pass1_control)
                        # print(pass1_control.arbitration_id)
                        if pass1_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584")
                            print(pass1_control)
                            # print("There is an answer ")
                            # print(pass1_control.data)
                            # print(state_control.data[4])
                        counter_pass1_temp += 1
                    print(" - -- - - - - - - - - - - - - - - PASS 2- -  - - - -  - - - -  - - - -  - - - - - - ")
                    pass2_to_send = [0x23, 0x01, 0x30, 0x02, 0x77, 0x77, 0x77, 0x77]
                    msg2 = can.Message(arbitration_id=BMS_tx_cobid, data=pass2_to_send, is_extended_id=False, dlc=8)
                    bus.send(msg2)
                    print("Sending message:")
                    print(msg2)
                    counter_pass2_temp = 0
                    while counter_pass2_temp < 10:  # send 5 times message to get answer 5 times
                        # (pilot signal change even if pilot is connected)
                        try:
                            print("Waiting for ACK and others respond")
                            # print("Message sent ok {}".format(bus.channel_info))
                            # print("data sent : " + str(pass2_to_send))
                        except can.CanError:
                            print("Message NOT sent")
                        pass2_control = bus.recv(0.25)
                        # print("CAN responds:")
                        # print(pass2_control)
                        # print(pass2_control.arbitration_id)
                        if pass2_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584")
                            print(pass2_control)
                            # print(pass2_control.data)
                            # print(state_control.data[4])
                        counter_pass2_temp += 1
                    print(" - -- - - - - - - - - - - - - - - change state - -  - - - -  - - - -  - - - -  - - - - - - ")
                    change_state_to_send = [0x23, 0x0b, 0x50, 0x04, 0x03, 0x0, 0x0, 0x0]
                    msg3 = can.Message(arbitration_id=BMS_tx_cobid, data=change_state_to_send, is_extended_id=False, dlc=8)
                    bus.send(msg3)
                    print("Sending message:")
                    print(msg3)
                    counter_state_can_temp = 0
                    while counter_state_can_temp < 10:  # send 5 times message to get answer 5 times
                        # (pilot signal change even if pilot is connected)
                        try:
                            print("Waiting for ACK and others respond")
                            # print("Message sent ok {}".format(bus.channel_info))
                            # print("data sent : " + str(msg3))
                        except can.CanError:
                            print("Message NOT sent")
                        state_can_control = bus.recv(0.25)
                        # print("CAN responds:")
                        # print(state_can_control)
                        # print(state_can_control.arbitration_id)
                        if state_can_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584: ")
                            print(state_can_control)
                            # print(state_can_control.data)
                            # print(state_control.data[4])
                        counter_state_can_temp += 1
                    print("Battery should be in sleep mode")
                    bus.shutdown()
                    can_module_change_result = self.actual_battery_state_readed()
                    print("change result from_can module: " + str(can_module_change_result))
                    if can_module_change_result == "SLEEP":
                        self.plainTextEdit.setPlainText("Stan zmieniono na:")
                        self.label_actual_state.setText(can_module_change_result)
                        self.add_data_to_log_file("State change active-->sleep by can module" + " | " +
                                                  "Readed state after change: " + can_module_change_result)
                    if can_module_change_result == "ACTIVE":
                        self.label_actual_state.setText("ERROR")
                        self.add_data_to_log_file("State change active-->sleep by can module" + " | " +
                                                  "Readed state after change: " + can_module_change_result + " | "
                                                  + "ERROR")
                except Exception as e:
                    print("---------------in state change(active -- > sleep) can module: " + str(e))
                    self.unexpected_error__Qmessage()
                    self.__init__()
        except Exception as e:
            print("---------------in change_from_active_to_sleep: " + str(e))


    def change_from_sleep_to_active(self):
        try:
            # print("start of change_from_sleep_to_active \n------------------------------------------------ ")
            self.pushButton_state_change_on_sleep.setEnabled(False)
            self.pushButton_state_change_on_active.setEnabled(False)
            self.label_actual_state.setText(" ")
            canopen_module_change_sleep_to_active_result = ""
            canopen_module_change_result_to_active = ""
            try:
                # ---------------------   canopen module ----------------------------------------
                print(" - -- - - - - - -  State change(sleep -- > active) canopen module - - - - - - - - - - - - - - ")
                bus = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                # Transmit SYNC every 100 ms
                network.sync.start(0.1)
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
                except Exception as e:
                    print("---------------sleep bit sending error: " + str(e))
                print("Battery should be in active mode")
                network.sync.stop()
                bus.disconnect()
                canopen_module_change_sleep_to_active_result = "change_OK"
                canopen_module_change_result_to_active = self.actual_battery_state_readed()
                print("change result from_canopen module: " + str(canopen_module_change_result_to_active))
            except Exception as e:
                print("---------------in tate change(sleep-- > active) canopen module: " + str(e))
                canopen_module_change_sleep_to_active_result = "change_error"
                if canopen_module_change_sleep_to_active_result == "change_OK"\
                        and canopen_module_change_result_to_active == "ACTIVE":
                    self.plainTextEdit.setPlainText("Stan zmieniono na:")
                    self.label_actual_state.setText(canopen_module_change_result_to_active)
                    self.add_data_to_log_file("State change sleep-->active by canopen module" + " | " +
                                              "Readed state after change: " + canopen_module_change_result_to_active)
            print(canopen_module_change_sleep_to_active_result)
            if canopen_module_change_sleep_to_active_result == "change_error" or \
                    canopen_module_change_result_to_active != "ACTIVE":
                try:
                    print("there was a problem in canopen module. Other module to change initialization(can)")
                    # ---------------------   can module ----------------------------------------
                    print(" - -- - - - - - -  State change(active -- > sleep) can module - - - - - - - - - - - - - - ")
                    print(" - -- - - - - - - - - - - - - - - PASS 1- -  - - - -  - - - -  - - - -  - - - - - - ")
                    bus = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                    pass1_to_send = [0x23, 0x01, 0x30, 0x01, 0x77, 0x77, 0x77, 0x77]
                    msg1 = can.Message(arbitration_id=BMS_tx_cobid, data=pass1_to_send, is_extended_id=False, dlc=8)
                    print("SENDING password 1 by can module")
                    print(msg1)
                    try:
                        bus.send(msg1)
                        # print("Message sent ok {}".format(bus.channel_info))
                        # print("data sent : " + str(to_send))
                    except can.CanError:
                        print("Message NOT sent")
                    counter_pass1_temp = 0
                    while counter_pass1_temp < 10:  # send 5 times message to get answer 5 times
                        # (pilot signal change even if pilot is connected)
                        try:
                            print("Waiting for ACK and others respond")
                            # print("Message sent ok {}".format(bus.channel_info))
                            # print("data sent : " + str(pass1_to_send))
                        except can.CanError:
                            print("Message NOT sent")
                        pass1_control = bus.recv(0.25)
                        # print("CAN responds:")
                        # print(pass1_control)
                        # print(pass1_control.arbitration_id)
                        if pass1_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584")
                            print(pass1_control)
                            # print("There is an answer ")
                            # print(pass1_control.data)
                            # print(state_control.data[4])
                        counter_pass1_temp += 1
                    print(" - -- - - - - - - - - - - - - - - PASS 2- -  - - - -  - - - -  - - - -  - - - - - - ")
                    pass2_to_send = [0x23, 0x01, 0x30, 0x02, 0x77, 0x77, 0x77, 0x77]
                    msg2 = can.Message(arbitration_id=BMS_tx_cobid, data=pass2_to_send, is_extended_id=False, dlc=8)

                    print("SENDING password 2 by can module")
                    print(msg2)
                    try:
                        bus.send(msg2)
                        # print("Message sent ok {}".format(bus.channel_info))
                        # print("data sent : " + str(to_send))
                    except can.CanError:
                        print("Message NOT sent")
                    counter_pass2_temp = 0
                    while counter_pass2_temp < 10:  # send 5 times message to get answer 5 times
                        # (pilot signal change even if pilot is connected)
                        try:
                            print("Waiting for ACK and others respond")
                            # print("Message sent ok {}".format(bus.channel_info))
                            # print("data sent : " + str(pass2_to_send))
                        except can.CanError:
                            print("Message NOT sent")
                        pass2_control = bus.recv(0.25)
                        # print("CAN responds:")
                        # print(pass2_control)
                        # print(pass2_control.arbitration_id)
                        if pass2_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584")
                            print(pass2_control)
                            # print(pass2_control.data)
                            # print(state_control.data[4])
                        counter_pass2_temp += 1
                    print(" - -- - - - - - - - - - - - - - - change state - -  - - - -  - - - -  - - - -  - - - - - - ")
                    change_state_to_send = [0x23, 0x0b, 0x50, 0x04, 0x02, 0x0, 0x0, 0x0]  # write "active function bits"
                    msg3 = can.Message(arbitration_id=BMS_tx_cobid, data=change_state_to_send, is_extended_id=False, dlc=8)

                    print("SENDING change state by can module")
                    print(msg3)
                    try:
                        bus.send(msg3)
                        # print("Message sent ok {}".format(bus.channel_info))
                        # print("data sent : " + str(to_send))
                    except can.CanError:
                        print("Message NOT sent")
                    counter_state_can_temp = 0
                    while counter_state_can_temp < 10:  # send 5 times message to get answer 5 times
                        # (pilot signal change even if pilot is connected)
                        try:
                            print("Waiting for ACK and others respond")
                            # print("Message sent ok {}".format(bus.channel_info))
                            # print("data sent : " + str(msg3))
                        except can.CanError:
                            print("Message NOT sent")
                        state_can_control = bus.recv(0.25)
                        # print("CAN responds:")
                        # print(state_can_control)
                        # print(state_can_control.arbitration_id)
                        if state_can_control.arbitration_id == 1412:  # hex 0x584 is 1412 in dec it is answer from BMZ
                            print("There is an answer from 0x584: ")
                            print(state_can_control)
                            # print(state_can_control.data)
                            # print(state_control.data[4])
                        counter_state_can_temp += 1
                    print("Battery should be back in active mode :)")
                    bus.shutdown()
                    can_module_result_in_sleep_to_active = self.actual_battery_state_readed()
                    print("change result from_can module: " + str(can_module_result_in_sleep_to_active))
                    if can_module_result_in_sleep_to_active == "ACTIVE":
                        self.plainTextEdit.setPlainText("Stan zmieniono na:")
                        self.label_actual_state.setText(can_module_result_in_sleep_to_active)
                        self.add_data_to_log_file("State change sleep-->active by can module" + " | " +
                                                  "Readed state after change: " + can_module_result_in_sleep_to_active)
                    if can_module_result_in_sleep_to_active == "SLEEP":
                        self.label_actual_state.setText("ERROR")
                        self.add_data_to_log_file("State change active-->sleep by can module" + " | " +
                                                  "Readed state after change: " + can_module_result_in_sleep_to_active
                                                  + " | " + "ERROR")
                except Exception as e:
                    print("---------------in tate change(sleep-- > active) can module: " + str(e))
                    self.unexpected_error__Qmessage()
        except Exception as e:
            print("---------------in change_from_sleep_to_active:  " + str(e))
            self.unexpected_error__Qmessage()

    def pushButton_connect_to_battery_click(self):

        global pilot_counter
        global can_converter_type
        global dir_path
        global log_files_path

        pilot_counter = 0
        battery_pilot = " "
        try:

            # print("start of pushButton_connect_to_battery_click \n------------------------------------------------ ")
            # print(can_converter_type)
            self.pushButton_state_change_on_sleep.setEnabled(False)
            self.pushButton_state_change_on_active.setEnabled(False)
            self.baterry_heartbeat_control_progress.setValue(0)
            self.battery_state_control_progress.setValue(0)
            self.plainTextEdit.setPlainText("Bateria jest w stanie:")
            self.label_actual_state.setText(" ")
            self.label_actual_serial_number.setText(" ")
            battery_heartbeat = ""
            repeated_battery_control = ""
            battery_heartbeat = self.heart_beat_control()
            # print(battery_heartbeat)
            if battery_heartbeat == "heartbeat Ok":
                # print('Beginning of pilot control')
                battery_pilot = self.pilot_control()
                # print(battery_pilot)
            if battery_heartbeat == "NO heartbeat":
                # print('There is no heartbeata')
                self.heartbeat_Qmessage()
            if battery_heartbeat == "Repeat need":
                # print('Repeat need')
                try_counter = 0
                while try_counter < 2:
                    try:
                        print(try_counter)
                        repeated_battery_control = self.heart_beat_control()
                        try_counter += 1
                        print(repeated_battery_control)
                    except Exception as e:
                        print("in pushButton_connect_to_battery_click: " + str(e))
                        repeated_battery_control = "NO heartbeat"
                print("heartbeat double control: " + str(repeated_battery_control))
                if repeated_battery_control == "heartbeat Ok":
                    # print('Beginning of pilot control')
                    battery_pilot = self.pilot_control()
                    # print(battery_pilot)
                if repeated_battery_control == "NO heartbeat":
                    # print('There is no heartbeata')
                    self.heartbeat_Qmessage()
                if repeated_battery_control == "Repeat need":
                    # print('There is no heartbeata')
                    self.heartbeat_Qmessage()
            print("End of pushButton_connect_to_battery_click function:")
            print("heartbeat: " + str(battery_heartbeat))
            if battery_heartbeat == "heartbeat Ok" or repeated_battery_control == "heartbeat Ok":
                print("Pilot : " + str(battery_pilot))
                if battery_pilot == "pilot OK":
                    print("Pilot present. Move forward ")
                    print("Reading serial number:")
                    battery_SN = self.read_battery_serial_number()
                    print(battery_SN)
                    if battery_SN != "ERROR":
                        self.label_actual_serial_number.setText(battery_SN)
                    if battery_SN == "ERROR":
                        self.SN_error__Qmessage()
                        self.label_actual_serial_number.setText("ERROR")
                    actual_battery_state_in_click = self.actual_battery_state_readed()
                    # print("Actual battery state:")
                    self.add_data_to_log_file("SN: " + str(battery_SN) + " | " + "Readed state: " +
                                              str(actual_battery_state_in_click))
                    if actual_battery_state_in_click == "ACTIVE":
                        self.label_actual_state.setText(actual_battery_state_in_click)
                        self.pushButton_state_change_on_sleep.setEnabled(True)
                    if actual_battery_state_in_click == "SLEEP":
                        self.label_actual_state.setText(actual_battery_state_in_click)
                        self.pushButton_state_change_on_active.setEnabled(True)
                    if actual_battery_state_in_click == "READ STATE ERROR":
                        self.label_actual_state.setText("ERROR")
                        self.unexpected_error__Qmessage()
                if battery_pilot == "No pilot":
                    self.pilot_Qmessage()
            battery_heartbeat = ""
            # print("End of pushButton_connect_to_battery_click \n------------------------------------------------ ")
        except Exception as e:
            print("in pushButton_connect_to_battery_click: " + str(e))

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
            # print(" - -- - - - - - - -  State of battery from canopen module - - - - - - - - - - - - - - - - - ")
            bus = network.connect(bustype='ixxat', channel=0, bitrate=500000)
            battery_serial_number = " "
            counter_state_temp_canopen_module = 0
            # Transmit SYNC every 100 ms
            network.sync.start(0.1)
            while counter_state_temp_canopen_module < 2:
                # print(counter)

                device_SN_1 = node.sdo.upload(0x6030, 1)  # check actual SN
                device_SN_2 = node.sdo.upload(0x6030, 2)  # check actual state object
                device_SN_3 = node.sdo.upload(0x6030, 3)  # check actual state object
                # print("Here is battery SN")
                # print(str(device_SN_1, 'utf-8'))
                # print(str(device_SN_2, 'utf-8'))
                # print(str(device_SN_3, 'utf-8'))
                battery_serial_number = (str(device_SN_1, 'utf-8') + str(device_SN_2, 'utf-8')
                                         + str(device_SN_3, 'utf-8'))
                # print(battery_serial_number)
                time.sleep(0.1)
                counter_state_temp_canopen_module += 1
            network.sync.stop()
            bus.disconnect()
            return battery_serial_number
            # print("End of read_battery_serial_number \n------------------------------------------------ ")
        except Exception as e:
            print("in read_battery_serial_number: " + str(e))
            return "ERROR"

    def actual_battery_state_readed(self):
        try:
            # print("start of actual_battery_state_readed \n------------------------------------------------ ")
            # ---------------------   canopen module ----------------------------------------

            # print(" - -- - - - - - - -  State of battery from canopen module - - - - - - - - - - - - - - - - - ")
            counter_state_temp_canopen_module = 0
            state_active_counter_canopen_module = 0
            state_sleep_counter_canopen_module = 0
            answer_from_canopen_module = ""
            try:
                bus_actual_battery_state_canopen = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                answer_from_canopen_module = ""
                # Transmit SYNC every 100 ms
                bus_actual_battery_state_canopen.sync.start(0.1)
                while counter_state_temp_canopen_module < 5:
                    # print(counter)
                    device_type_data = node.sdo.upload(0x500b, 4)  # check actual state object
                    # print(device_type_data)
                    time.sleep(0.1)
                    if device_type_data == b'\x02':                 # 2 if battery is in ACTIVE mode
                        # print('Is active')
                        state_active_counter_canopen_module += 1
                        # actual_battery_state = 2
                    if device_type_data == b'\x03':                 # 3 if battery is in SLEEP mode
                        state_sleep_counter_canopen_module += 1
                        # actual_battery_state = 3  # 3 if battery is in SLEEP mode
                        # print("Is sleep")
                    counter_state_temp_canopen_module += 1
                bus_actual_battery_state_canopen.sync.stop()
                bus_actual_battery_state_canopen.disconnect()
            except Exception as e:
                print("in state of battery from canopen module: " + str(e))
            # print("State of battery according to canopen module? ")
            # print("Active: " + str(state_active_counter_canopen_module) +
            #      ".  Sleep: " + str(state_sleep_counter_canopen_module))
            if state_active_counter_canopen_module < state_sleep_counter_canopen_module:
                # print("Sleep in canopen module")
                answer_from_canopen_module = "SLEEP"
            if state_active_counter_canopen_module > state_sleep_counter_canopen_module:
                # print("Active in canopen module")
                answer_from_canopen_module = "ACTIVE"
            # ---------------------   can module ----------------------------------------
            # print(" - -- - - - - - - -  State of battery from can module - - - - - - - - - - - - - - - - - ")
            state_active_counter_can_module = 0
            state_sleep_counter_can_module = 0
            answer_from_can_module = ""
            try:
                bus_actual_battery_state_can = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                # data sent in SDO to Read Dictionary Object
                # [Byte 0       ,Byte 1, Byte 2,Byte 3,	    Byte 4,	Byte 5,	Byte 6,	Byte 7]
                # [Command Code ,Index,         Sub Index	Data]
                # index is reversed
                # to_send = [64, 1, 64, 6, 0, 0, 0, 0]
                to_send = [0x40, 0x0b, 0x50, 0x04, 0x0, 0x0, 0x0, 0x0]
                msg = can.Message(arbitration_id=BMS_tx_cobid, data=to_send, is_extended_id=False, dlc=8)
                # print(msg)
                counter_state_temp = 0
                while counter_state_temp < 5:                    # send 5 times message to get answer 5 times
                                                            # (pilot signal change even if pilot is connected)
                    try:
                        bus_actual_battery_state_can.send(msg)
                        # print("Message sent ok {}".format(bus.channel_info))
                        # print("data sent : " + str(to_send))
                    except can.CanError:
                        print("Message NOT sent")
                    state_control = bus_actual_battery_state_can.recv(0.25)
                    # print(state_control)
                    # print(state_control.arbitration_id)
                    if state_control.arbitration_id == 1412:        # hex 0x584 is 1412 in dec it is answer from BMZ
                        # print("There is an answer ")
                        # print(state_control.data)
                        # print(pilot_control.data[4])                # get value from bytearray- this byte have 0 or 1
                        if state_control.data[4] == 2:
                            # print('Is active')
                            state_active_counter_can_module += 1
                        if state_control.data[4] == 3:
                            # print("Is sleep")
                            state_sleep_counter_can_module += 1
                    counter_state_temp += 1

                # print(pilot_control)
                bus_actual_battery_state_can.shutdown()
            except Exception as e:
                print("in  state of battery from can module: " + str(e))
            # print("State of battery according to  can module: ")
            # print("Active: " + str(state_active_counter_can_module) +
            #      ".  Sleep: " + str(state_sleep_counter_can_module))

            if state_active_counter_can_module < state_sleep_counter_can_module:
                # print("Sleep in canopen module")
                answer_from_can_module = "SLEEP"
            if state_active_counter_can_module > state_sleep_counter_can_module:
                # print("Active in canopen module")
                answer_from_can_module = "ACTIVE"
            print("Both module say:")
            print(answer_from_canopen_module, answer_from_can_module)
            if answer_from_canopen_module == "ACTIVE" and answer_from_can_module == "ACTIVE":
                return "ACTIVE"
            if answer_from_canopen_module == "SLEEP" and answer_from_can_module == "SLEEP":
                return "SLEEP"
            else:
                return "READ STATE ERROR"

        except Exception as e:
            print("in actual_battery_state_readed: " + str(e))
            return "READ STATE ERROR"

    def heart_beat_control(self):
        try:
            # print("start of heart_beat_control \n------------------------------------------------ ")
            canopen_control_needed = ""
            # -----------------------   can module ------------------------------------------------

            try:
                print("start heart_beat_control by can module")
                bus2 = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                counter_for_heartbeat_control = 1
                heart_beat_counter = 0
                while counter_for_heartbeat_control < 10:
                    # print(counter_for_heartbeat_control)
                    heart_beat_control = bus2.recv(0.1)
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
                    self.baterry_heartbeat_control_progress.setValue(int(counter_for_heartbeat_control))
                print("heartbeat count")
                print(heart_beat_counter)
                if heart_beat_counter != 0:
                    # print("heartbeat Ok ")
                    bus2.shutdown()
                    return "heartbeat Ok"
                if heart_beat_counter == 0:
                    # print("NO heartbeat")
                    bus2.shutdown()
                    canopen_control_needed = "need start canopen control"
                    # return "NO heartbeat"
                # print("state of CAN'a:      {}".format(bus.state))
            except Exception as e:

                print("in can module of heart_beat_control: " + str(e))
                canopen_control_needed = "need start canopen control"
            # ---------------------   canopen module ----------------------------------------
            canopen_module_heart_answer = ""
            if canopen_control_needed == "need start canopen control":
                try:
                    print(" start heartbeat control by canopen module")
                    bus_canmodule_heartbeat = network.connect(bustype='ixxat', channel=0, bitrate=500000)

                    # print(bus_canmodule_heartbeat)
                    counter_temp = 0
                    # Transmit SYNC every 100 ms
                    bus_canmodule_heartbeat.sync.start(0.1)
                    while counter_temp < 5:
                        try:
                            bus_canmodule_heartbeat.send_message(0x0, [0x1, 0])
                            print("waiting for heartbeat ")
                            canopen_module_heart_answer = node.nmt.wait_for_heartbeat(timeout=2)
                        except Exception as e:
                            print("in canopen module of heart_beat_control1: " + str(e))
                        counter_temp += 1
                        temp_for_progress_bar = 2 * counter_temp
                        print(canopen_module_heart_answer)
                        self.baterry_heartbeat_control_progress.setValue(int(temp_for_progress_bar))

                    try:
                        bus_canmodule_heartbeat.sync.stop()
                        bus_canmodule_heartbeat.disconnect()
                    except Exception as e:
                        print("in canopen module of heart_beat_control_ turn off bus: " + str(e))

                    if canopen_module_heart_answer == "OPERATIONAL":
                        return "heartbeat Ok"
                    if canopen_module_heart_answer != "OPERATIONAL":
                        return "NO heartbeat"
                except Exception as e:
                    print("in canopen module of heart_beat_control2: " + str(e))
                    return "NO heartbeat"

        except Exception as e:
            print("in heart_beat_control: " + str(e))
            return "Repeat need"

    def pilot_control(self):
        try:
            print("start of pilot_control \n------------------------------------------------ ")
            try:
                pilot_counter_in_canopen_module = 0
                # ---------------------   canopen module ----------------------------------------
                # print("- -- - - - - - - -  pilot control in canopen module")
                bus_pilot_control_canopen = network.connect(bustype='ixxat', channel=0, bitrate=500000)
                counter_temp = 0
                # Transmit SYNC every 100 ms
                bus_pilot_control_canopen.sync.start(0.05)
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

            except Exception as e:
                print("in pilot_control canopen module: " + str(e))
                pilot_counter_in_canopen_module = 0
            # ----------------------------------------------------------------------------------
            # -----------------------   can module ----------------------------------------
            try:
                # print(" - -- - - - - - - -  pilot control in can module - second check")
                bus_pilot_control_can = can.interface.Bus(bustype='ixxat', channel='0', bitrate=500000)
                # data sent in SDO to Read Dictionary Object
                # [Byte 0       ,Byte 1, Byte 2,Byte 3,	    Byte 4,	Byte 5,	Byte 6,	Byte 7]
                # [Command Code ,Index,         Sub Index	Data]
                # index is reversed
                # to_send = [64, 1, 64, 6, 0, 0, 0, 0]
                to_send = [0x40, 0x01, 0x40, 0x06, 0x0, 0x0, 0x0, 0x0]
                msg = can.Message(arbitration_id=BMS_tx_cobid, data=to_send, is_extended_id=False, dlc=8)
                # print(msg)
                pilot_counter_in_can_module = 0

                while counter_temp < 10:                    # send 5 times message to get answer 5 times
                                                            # (pilot signal change even if pilot is connected)
                    try:
                        bus_pilot_control_can.send(msg)
                        # print("Message sent ok {}".format(bus.channel_info))
                        # print("data sent : " + str(to_send))
                    except can.CanError:
                        print("Message NOT sent")
                    pilot_control = bus_pilot_control_can.recv(0.25)
                    # print(pilot_control)
                    # print(pilot_control.arbitration_id)
                    if pilot_control.arbitration_id == 1412:          # hex 0x584 is 1412 in dec
                        # print("There is an answer ")
                        # print(pilot_control.data)
                        # print(pilot_control.data[4])                # get value from bytearray- this byte have 0 or 1
                        if pilot_control.data[4] != 0:
                            pilot_counter_in_can_module += 1
                    counter_temp += 1
                    self.battery_state_control_progress.setValue(int(counter_temp))
                # print(pilot_control)
                bus_pilot_control_can.shutdown()
                # print("heartbeaty:" )
                # print("w module net, w module can")
                # print(pilot_counter_in_canopen_module, pilot_counter_in_can_module)
            except Exception as e:
                print("in pilot_control can module: " + str(e))
                pilot_counter_in_can_module = 0

            if pilot_counter_in_canopen_module != 0 or pilot_counter_in_can_module != 0:
                print("Pilot found in modules!!!!!!")
                print(pilot_counter_in_canopen_module, pilot_counter_in_can_module)
                return "pilot OK"
            else:
                # print("No pilot in modules")
                self.pilot_Qmessage()
                return "No pilot"
        except Exception as e:
            print("in pilot_control: " + str(e))
            self.pilot_Qmessage()
            return "No pilot"

    def can_converter_control(self):
        try:
            # print("start of can_converter_control \n------------------------------------------------ ")
            
            global can_converter_type
            
            # global peak_present
            # try:
            # print("Start of Thread_can_converter_check ixxata conection ")
            # network.connect(bustype='ixxat', channel=0, bitrate=500000)
            # network.sync.start(0.1)
            # self.thread_can_converter_check_out = "IXXAT connect"
            # time.sleep(0.5)
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

    def can_converter_reset(self):
        try:
            # print("start of can_converter_reset \n------------------------------------------------ ")

            global can_converter_type
            converter_reset = network.connect(bustype='ixxat', channel=0, bitrate=500000)
            converter_reset.clear()
            converter_reset.disconnect()
            print("End of can_converter_reset\n------------------------------------------------ ")
        except Exception as et:
            print("in can_converter_reset: " + str(et))
            
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
            self.__init__()
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
            self.__init__()
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
            self.__init__()
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))

# ###################################################################################################################
    # #####################################     Log_error__Qmessage       ########################################
    def SN_error__Qmessage(self):
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Nie można odczytać numeru seryjnego baterii.\nLog nie zostanie utworzony\n"
                        "Zalecany reset aplikacji")

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
            self.__init__()
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
            self.__init__()
        except Exception as e:
            print("---------------In network_Qmessage: " + str(e))


if __name__ == '__main__':

    app = QApplication(sys.argv)
    ex = State_changer_mainWindow()
    ex.show()
    sys.exit(app.exec_())
# ###################################################################################################################
