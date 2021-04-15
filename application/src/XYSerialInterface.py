import serial
from constants import *
from EndstopBox import EndstopBox
import re

import port_finder

try:
    from ports_serial import *
except:
    print("No port configuration found! Running Port Configuration Utility...")
    port_finder.configure_and_commit()

from ports_serial import *


class XYSerialInterface:
    def __init__(self):  # two serial interfaces, one with X and one with Y uStepper
        """Create the interface"""
        self.allocatePorts()  # allocates its ports
        self.initialisePosition()
        self.isBlocking = 0
        self.boundsController = EndstopBox()

        self.getBounds()

    def getBounds(self):
        if GET_BOUNDS_ON_STARTUP:
            self.homeBoth()

    def allocatePorts(self):
        """Allocate and connect to X and Y ports."""
        flag = 1

        while flag:

            print("connecting to steppers")
            try:
                for comport in serial.tools.list_ports.comports():
                    if comport.serial_number == STAGE_X_SERIAL_NUMBER:
                        self.portX = serial.Serial(comport.name, 115200, timeout=1)
                    elif comport.serial_number == STAGE_Y_SERIAL_NUMBER:
                        self.portY = serial.Serial(comport.name, 115200, timeout=1)

                self.portX
                self.portY
                flag = 0
            except:
                flag = 1
                i = input(
                    "Unable to connect to steppers. Would you like to retry (r) or reconfigure (c)?"
                )
                if i == "c":
                    port_finder.configure_and_commit()

    def initialisePosition(self):
        self.currentPosition = {}
        self.currentPosition[0] = 0
        self.currentPosition[1] = 30

    def getCurrentPosition(self):
        return self.currentPosition

    def move(self, axis, steps):
        """Move a given number of steps relative to the current position

        :param axis: Axis to move
        :type axis: int
        :param steps: Number of steps to move
        :type steps: int
        """

        self.command(axis, self.Gmove(steps))
        # print(dimMap[axis] +" " + str(steps) + " steps")

    def moveStepsAbsolute(self, axis, steps):
        """Move to an absolute position in steps

        :param axis: Axis to move
        :type axis: int
        :param steps: Absolute step to move to
        :type steps: int
        """

        diff = int(steps - self.currentPosition[axis])
        print(diff)
        self.move(axis, diff)

    def moveAngleAbsolute(self, axis, angle):
        """Move to an absolute angle

        :param axis: axis to move
        :type axis: int
        :param angle: angle to move to
        :type angle: float
        """
        self.command(axis, self.GmoveAngleAbsolute(angle))

    def homeBoth(self):
        """Home both motors and reset their zero point"""
        self.boundsController.maximumAngle[0] = self.home(0)
        self.boundsController.maximumAngle[1] = self.home(1)
        print("Rail lengths found: " + str(self.boundsController.maximumAngle))

    def home(self, axis):
        """Home a motor and return the distance it homed

        :param axis: Axis to home
        :type axis: bool
        :return: Rail length in degrees
        :rtype: float
        """
        self.command(axis, self.Ghome())
        dataDict = self.blockUntilRX(axis, "DATA", True)
        return dataDict["A"]

    def command(self, axis, data):
        """Sends a serial command to the specified axis

        :param axis: Axis to which the command is sent
        :type axis: int
        :param data: The command to be sent
        :type data: string
        """
        self.axisToPort(axis).write(data)

    def blockUntilRX(self, axis, msg, passToParser):
        """Block until a specific message is reveived from the stepper

        :param axis: Axis to block
        :type axis: int
        :param msg: Message to wait for
        :type msg: string
        :param passToParser: If True, the message returned will be sent to the parser
        :type passToParser: bool
        :return: A dictionary containing data parsed from the message
        :rtype: dict
        """
        self.isBlocking = 1
        port = self.axisToPort(axis)
        print("blocking axis " + str(axis))

        flag = 0
        while flag == 0:

            msgRX = port.readline()
            msgRX = msgRX.decode("utf-8")
            # print(msgRX)
            if msg in msgRX:
                flag = 1
                print("unblock axis " + str(axis))  #
        self.isBlocking = 0
        if passToParser:

            dict1 = self.parseData(msgRX)
            return dict1

    def axisToPort(self, axis):
        if axis == 0:
            return self.portX
        if axis == 1:
            return self.portY

    def stopAll(self):
        """Stop all motors."""
        self.stop(1)
        self.stop(0)

    def stop(self, axis):
        """Stop motion on a given axis

        :param axis: axis to stop
        :type axis: int
        """
        self.command(axis, self.Gstop())

    def Gmove(self, steps):
        datastring = "G0 A" + str(steps) + "\n"
        return datastring.encode("utf-8")

    def GmoveAngleAbsolute(self, angle):
        """Generates GCode G1 to move the motor to a specified angle"""
        string = "G1 A" + str(angle) + "\n"
        return string.encode("utf-8")

    def Ghome(self):
        """Generates GCode G4 to home the motor. at some point I should make the direction configurable"""
        datastring = (
            "G4 V100 T2 D1\n"  # hardocded a threshold of 2 for now. seems to work fine.
        )
        return datastring.encode("utf-8")

    def GgetData(self):
        """Generates GCode M15 to request positional data"""
        datastring = "M15 \n"
        return datastring.encode("utf-8")

    def GgetTempData(self):
        """Generates GCode M17 to request temperature data"""
        datastring = "M17 \n"
        return datastring.encode("utf-8")

    def Gstop(self):
        """Generates GCode M0 to stop a motor"""
        datastring = "M0 \n"
        return datastring.encode("utf-8")

    def getData(self, axis):
        # print('getting status')
        reply = self.callResponse(self.GgetData(), self.axisToPort(axis))
        # print(reply)
        parsed = self.parseData(reply)
        # print(parsed)
        return parsed

    def getTempData(self, axis):
        reply = self.callResponse(self.GgetTempData(), self.axisToPort(axis))
        parsed = self.parseData(reply)
        return parsed

    def trigger(self, axis, trigger):
        if trigger == "A":
            msg = self.GTriggerA()
        elif trigger == "B":
            msg = self.GTriggerB()
        self.command(axis, msg)

    def setDurations(self, axis, delay, led, second, tog):
        msg = self.GSetDurations(delay, led, second, tog)
        self.command(axis, msg)

    def GTriggerA(self):
        datastring = "M19 \n"
        return datastring.encode("utf-8")

    def GSetDurations(self, delay, led, second, tog):  # duration should be in us
        tog = int(tog == True)
        datastring = (
            "M18 D"
            + str(delay)
            + " L"
            + str(led)
            + " S"
            + str(second)
            + " T"
            + str(tog)
            + " \n"
        )
        return datastring.encode("utf-8")

    def parseData(self, data):
        """parse data provided in format DATA A0.03 S0 V0.00 D0.00 from the M15 Gcode.

        :param data: data from the uStepper in response to an M15 GCode
        :type data: string
        :return: a dictionary with the data in
        :rtype: dict
        """

        seps = re.split(":? ", data)
        datadict = {}
        try:
            for s in seps:
                if (s != "DATA") and (s != "TEMP"):
                    label = s[0]
                    val = re.findall(
                        r"[-+]?\d*\.\d+|\d+", s
                    )  # weird regex. just trust it.
                    val = float(val[0])
                    datadict[label] = val
        except IndexError:
            print("Something went wrong parsing: " + data)
        return datadict

    def callResponse(self, message, port):
        """take a port and a message for that port and returns the response given by the uStepperS

        :param message: [description]
        :type message: [type]
        :param port: [description]
        :type port: [type]
        :return: [description]
        :rtype: [type]
        """
        # print(message)
        port.reset_input_buffer()
        port.write(message)
        msg = port.readline()
        # print(msg)
        return msg.decode("utf-8")
