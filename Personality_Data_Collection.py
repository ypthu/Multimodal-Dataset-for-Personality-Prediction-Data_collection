#! /usr/bin/env python
#  -*- coding:utf-8 -*-
from psychopy import visual, core, event, gui
import random
import numpy as np
import sys
import pandas as pd
# import serial
import time
import os
import threading
import cv2
import csv
import paho.mqtt.client as mqtt
from neuracle_lib.triggerBox import TriggerBox,TriggerIn,PackageSensorPara
import time

from pyorbbecsdk import *
from utils import frame_to_bgr_image

DEBUG = True
DEBUG_ = True
HOST = '192.168.31.150'
PORT = 1883

# EEG trigger port



SERIAL_PORT = 'COM6'

rootpath='./'
sub_no = None
# Operation type
TYPE_IMG = 1
TYPE_VIDEO = 2
TYPE_TXT = 3
TYPE_QUESTIONNAIRE = 4
PRACTICE_VID = 50
REST_VID = 40
RESTING_STATE_DUR = 60*2
LANG='ch'


triggerObj = None
flag = None

def InitGlobal():
    # Create trigger object
    global triggerObj

    if not DEBUG:
        triggerObj = EEGTrigger(SERIAL_PORT)

    # Create control flag for camera
    global flag
    flag = ''

# customized slider
class MySlider():
    def __init__(self,
                 win,
                 emo_label=None,
                 ticks=[1, 2, 3, 4, 5, 6, 7, 8, 9],
                 labels=None,
                 startValue=None,
                 pos=(0, 0),
                 size=[1.0, 0.05],
                 units=None,
                 flip=False,
                 ori=0,
                 style='tickLines', styleTweaks=[],
                 granularity=0,
                 readOnly=False,
                 labelColor='White',
                 markerColor='Red',
                 lineColor='White',
                 colorSpace='rgb',
                 opacity=None,
                 font='Helvetica Bold',
                 depth=0,
                 name=None,
                 labelHeight=None,
                 labelWrapWidth=None,
                 autoDraw=False,
                 autoLog=True,
                 # Synonyms
                 color=False,
                 fillColor=False,
                 borderColor=False
                 ):
        # self.slider = visual.Slider(win, pos=pos, style='slider', fillColor='red', borderColor='Red', granularity=0.1, ticks=[0,1,2,3,4,5,6,7,8,9], labels=[0,1,2,3,4,5,6,7,8,9],colorSpace='rgb')
        self.rect = visual.Rect(win, width=1.2 * size[0], height=size[1], lineColor='green', pos=pos)
        self.slider = visual.Slider(win, pos=pos, style='scrollbar', fillColor='green', borderColor='green',
                                    granularity=1.0, size=size,
                                    ticks=ticks, labels=labels,
                                    colorSpace='rgb')
        self.score = visual.TextStim(win, text='None', pos=(pos[0] + 0.65, pos[1]), height=size[1])
        if emo_label is None:
            self.emo_label = None
        else:
            self.emo_label = visual.TextStim(win, emo_label, pos=(pos[0] - size[0] / 2 - 0.25, pos[1]), height=size[1])
    
    def draw(self):
        self.rect.draw()
        self.slider.draw()
        score = self.slider.getRating()
        
        if score is None:
            self.score.setColor('red')
        else:
            self.score.setColor('white')
        self.score.setText(score)
        self.score.draw()
        self.emo_label.draw()
    
    def getRating(self):
        return self.slider.getRating()

class RatingPage():
    def __init__(self, win, emos, ticks=[1, 2, 3, 4, 5, 6, 7, 8, 9], instructions='请根据您当前的情绪状态，选择以下每一种情绪\n的强度。1表示一点都没有，9表示非常强:', labels=None, fix_indx = 0):
        self.emos = emos
        self.instruct = visual.TextStim(win, text=instructions, pos=(-0.6, 0.85), wrapWidth=0.1)
        self.sliders = {}
        hStart = (len(emos) - 1) // 2 * 0.15
        hs = [0.3, 0.1, -0.1]
        if labels is None:
            labels = ticks
        nCur = 0
        
        # emos_s = emos.copy()
        if fix_indx != 0:
            emos_s = emos[:fix_indx]
            random.shuffle(emos_s)
            emos_s = emos_s + emos[fix_indx:]
        else:
            emos_s = emos.copy()
            random.shuffle(emos_s)
        
        for emo in emos_s:
            self.sliders[emo] = MySlider(win, ticks=ticks, labels=labels, pos=[0, hStart - 0.15 * nCur], emo_label=emo)
            nCur = nCur + 1
    
    def draw(self):
        self.instruct.draw()
        for emo in self.emos:
            self.sliders[emo].draw()
    
    def getRating(self):
        rts = {}
        
        for emo in self.emos:
            rts[emo] = self.sliders[emo].getRating()
        
        return rts
    
    def isReady(self):
        ready = True
        # ready = (self.sliders.getRating() is not None)
        for emo in self.emos:
            if self.sliders[emo].getRating() is None:
                ready = False
                break
        return ready


class ImgRatingPage():
    def __init__(self, win, emos, img, ticks=[1, 2, 3, 4, 5, 6, 7, 8, 9],
                 instructions='请根据您当前的情绪状态，选择以下每一种情绪\n的强度。1表示一点都没有，9表示非常强:',
                 labels=None, fix_indx=0):
        self.emos = emos
        self.instruct = visual.TextStim(win, text=instructions, pos=(-0.6, 0.85), wrapWidth=0.1)
        self.sliders = {}
        
        hStart = (len(emos) - 1) // 2 * 0.15-0.5
        hs = [0.3, 0.1, -0.1]
        if labels is None:
            labels = ticks
        nCur = 0
        
        # emos_s = emos.copy()
        if fix_indx != 0:
            emos_s = emos[:fix_indx]
            random.shuffle(emos_s)
            emos_s = emos_s + emos[fix_indx:]
        else:
            emos_s = emos.copy()
            random.shuffle(emos_s)
        
        for emo in emos_s:
            self.sliders[emo] = MySlider(win, ticks=ticks, labels=labels, pos=[0, hStart - 0.15 * nCur], emo_label=emo)
            nCur = nCur + 1
        
        img_stim = visual.ImageStim(win,pos=[0,0.2])
        img_stim.image = img
        self.img = img_stim
    
    def draw(self):
        self.img.draw()
        self.instruct.draw()
        for emo in self.emos:
            self.sliders[emo].draw()
    
    def getRating(self):
        rts = {}
        
        for emo in self.emos:
            rts[emo] = self.sliders[emo].getRating()
        
        return rts
    
    def isReady(self):
        ready = True
        # ready = (self.sliders.getRating() is not None)
        for emo in self.emos:
            if self.sliders[emo].getRating() is None:
                ready = False
                break
        return ready
    
class MQTT():
    def __init__(self, HOST='183.173.199.25', PORT=1883, filepath='./'):
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(HOST, PORT, 60)
        # subscribe message
        self.client.subscribe('d/dev-sensing/+/raw/gsr')
        self.client.subscribe('d/dev-sensing/+/raw/ppg')
        self.client.subscribe("d/dev-sensing/+/feature/gsr")
        self.client.subscribe("d/dev-sensing/+/feature/ppg")
        # self.client.subscribe('d/dev-sensing/4049974370/raw/gsr')
        # self.client.subscribe('d/dev-sensing/4049974370/raw/ppg')
        # self.client.subscribe("d/dev-sensing/4049974370/feature/gsr")
        # self.client.subscribe("d/dev-sensing/4049974370/feature/ppg")
        # self.client.subscribe("c/dev-sensing/resting-collect/one/4050156530")
        # self.client.subscribe("d/dev-sensing/+/status")
        # self.client.subscribe("d/dev-sensing/+/operation/")
        self.marker = [0,0,0,0] #[0,1,2,3]  indexes 0-3 for raw_ppg, raw_gsr, fea_ppg, fea_gsr respectively.
        self.rawfile = None
        # check if the directory exists
        if not os.path.exists(filepath):
            os.makedirs(filepath)
        
        self.raw_gsr = open(os.path.join(filepath, 'raw_gsr.csv'), 'a', newline='')
        self.raw_ppg = open(os.path.join(filepath, 'raw_ppg.csv'), 'a', newline='')
        self.fea_gsr = open(os.path.join(filepath, 'fea_gsr.csv'), 'a', newline='')
        self.fea_ppg = open(os.path.join(filepath, 'fea_ppg.csv'), 'a', newline='')
        self.data={}
        self.csv_rgsr = csv.writer(self.raw_gsr)
        self.csv_rppg = csv.writer(self.raw_ppg)
        self.csv_fgsr = csv.writer(self.fea_gsr)
        self.csv_fppg = csv.writer(self.fea_ppg)
        
    def __del__(self):
        if self.rawfile is not None:
            self.raw_gsr.close()
            self.raw_ppg.close()
            self.fea_gsr.close()
            self.fea_ppg.close()
        
        
    def setMarker(self, value):
        self.marker = [value,value,value,value]

        # 连接成功回调
    def loop_start(self):
        self.client.loop_start()
        
    def loop_stop(self):
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc):
        DebugInfo('Connected with result code' + str(rc))

    # 消息接收回调
    def _on_message(self, client, userdata, msg):
        DebugInfo("topic:" + msg.topic + "-payload:" + str(msg.payload))
        parts = msg.topic.split('/')
        datas = eval(msg.payload)
        data = datas['data']
        if len(data) == 0:
            DebugInfo('No data')
            return
        timestamp = str(datas['timestamp'])
        
        #DEBUG('Timestamp:' + timestamp)
        marker = 0

        if parts[-2] == 'raw':
            if parts[-1] == 'ppg':
                writer = self.csv_rppg
                if self.marker[0] > 0:
                    marker = self.marker[0]
                    self.marker[0] = 0
                
            elif parts[-1] == 'gsr':
                writer = self.csv_rgsr
                if self.marker[1] > 0:
                    marker = self.marker[1]
                    self.marker[1] = 0
            else:
                print('Invalid topic:', msg.topic)
                return
        elif parts[-2] == 'feature':
            if parts[-1] == 'ppg':
                writer = self.csv_fppg
                if self.marker[2] > 0:
                    marker = self.marker[2]
                    self.marker[2] = 0
            elif parts[-1] == 'gsr':
                writer = self.csv_fgsr
                if self.marker[3] > 0:
                    marker = self.marker[3]
                    self.marker[3] = 0
            else:
                print('Invalid topic:', msg.topic)
                return
        else:
            print('Invalid topic:', msg.topic)
            return

        # prepare rows
        if marker > 0:
            rows = [(timestamp, data[0], marker)]

        else:
            rows = [(timestamp, data[0])]
        
        for value in data[1:]:
            rows = rows+[('', value)]
        
        writer.writerows(rows)

# Print debug infomation in debug mode
def DebugInfo(text):
    if DEBUG_:
        print(text)


# Thread class for video capture
# added by yangpei for video capture
# 'flag' is a global variable, and we can use it to control the camera state (values for 'flag':'start'/'stop').
#

def StartCamera():
    global flag
    flag = 'start'
    SendMarker(-1, 0, eeg=False)
    
def StopCamera():
    global flag
    flag = 'stop'
    SendMarker(-1, 1, eeg=False)

class IRCameraRecorder(threading.Thread):
    def __init__(self, name, param):
        threading.Thread.__init__(self, name=name)
        self.param = param
        self.isrun = False
        self.hfile = None
        self.config = Config()
        
        self.context = Context()
        devices = self.context.query_devices()
        device = devices.get_device_by_index(0)
        device.set_bool_property(OBPropertyID.OB_PROP_LASER_BOOL, True)
        self.pipeline = Pipeline()
    
    def run(self):
        while True:
            global flag
            if flag == 'start' and self.isrun is False:
                try:
                    # devices = self.context.query_devices()
                    # device = devices.get_device_by_index(0)
                    # device.set_bool_property(OBPropertyID.OB_PROP_LASER_BOOL, True)
                    profile_list = self.pipeline.get_stream_profile_list(OBSensorType.IR_SENSOR)
                    try:
                        ir_profile = profile_list.get_video_stream_profile(640, 0, OBFormat.Y16, 30)
                    except OBError as e:
                        print(e)
                        ir_profile = profile_list.get_default_video_stream_profile()
                    self.config.enable_stream(ir_profile)
                except Exception as e:
                    print(e)
                    return
                
                self.pipeline.start(self.config)
                
                # self.camera = cv2.VideoCapture(0)
                # self.camera.set(cv2.CAP_PROP_SETTINGS,1)
                # self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                # self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                # frame_size = (int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                frame_fps = 20
                video_format = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
                self.hfile = cv2.VideoWriter()
                filepath = self.param[:-4] + '_'+str(int(round(time.time()*1000))) + self.param[-4:]
                self.hfile.open(filepath, video_format, ir_profile.get_fps(), (ir_profile.get_width(), ir_profile.get_height()))
                self.isrun = True
            
            elif flag == 'stop':
                self.isrun = False
                self.hfile.release()
                devices = self.context.query_devices()
                device = devices.get_device_by_index(0)
                device.set_bool_property(OBPropertyID.OB_PROP_LASER_BOOL, False)
                self.pipeline.stop()
                print('Thread finished.')
                return
            
            if self.isrun:
                frames = self.pipeline.wait_for_frames(100)
                if frames is None:
                    continue
                ir_frame = frames.get_ir_frame()
                if ir_frame is None:
                    continue
                ir_data = np.asanyarray(ir_frame.get_data())
                width = ir_frame.get_width()
                height = ir_frame.get_height()
                
                ir_format = ir_frame.get_format()
                if ir_format == OBFormat.Y8:
                    ir_data = np.resize(ir_data, (height, width, 1))
                    data_type = np.uint8
                    image_dtype = cv2.CV_8UC1
                    max_data = 255
                elif ir_format == OBFormat.MJPG:
                    ir_data = cv2.imdecode(ir_data, cv2.IMREAD_UNCHANGED)
                    data_type = np.uint8
                    image_dtype = cv2.CV_8UC1
                    max_data = 255
                    if ir_data is None:
                        print("decode mjpeg failed")
                        continue
                    ir_data = np.resize(ir_data, (height, width, 1))
                else:
                    ir_data = np.frombuffer(ir_data, dtype=np.uint16)
                    data_type = np.uint16
                    image_dtype = cv2.CV_16UC1
                    max_data = 65535
                    ir_data = np.resize(ir_data, (height, width, 1))
                # cv2.normalize(ir_data, ir_data, 0, max_data, cv2.NORM_MINMAX, dtype=image_dtype)
                ir_data = ir_data.astype(data_type)
                ir_image = cv2.cvtColor(ir_data, cv2.COLOR_GRAY2RGB)
                
                # cv2.imshow("Infrared Viewer", ir_image)
                self.hfile.write(ir_image)
                # if int(round(time.time())) -self.t > 30:
                #     self.flag = 'stop'
            else:
                time.sleep(0.005)

class ColorCameraRecorder(threading.Thread):
    def __init__(self, name, param):
        threading.Thread.__init__(self, name=name)
        self.param = param
        self.isrun = False
        self.hfile = None
        self.config = Config()
        self.pipeline = Pipeline()
        self.context = Context()

    
    def run(self):
        while True:
            global flag
            if flag == 'start' and self.isrun is False:
                try:
                    profile_list = self.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
                    try:
                        color_profile = profile_list.get_video_stream_profile(640, 0, OBFormat.RGB, 30)
                    except OBError as e:
                        print(e)
                        color_profile = profile_list.get_default_video_stream_profile()
                    self.config.enable_stream(color_profile)
                except Exception as e:
                    print(e)
                    return
                
                self.pipeline.start(self.config)
                
                video_format = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
                self.hfile = cv2.VideoWriter()
                filepath = self.param[:-4] + '_' + str(int(round(time.time() * 1000))) + self.param[-4:]
                self.hfile.open(filepath, video_format, color_profile.get_fps(),
                                (color_profile.get_width(), color_profile.get_height()))
                self.isrun = True
            
            elif flag == 'stop':
                self.isrun = False
                self.hfile.release()
                
                self.pipeline.stop()
                print('Thread finished.')
                return
            
            if self.isrun:
                frames = self.pipeline.wait_for_frames(100)
                if frames is None:
                    continue
                color_frame = frames.get_color_frame()
                if color_frame is None:
                    continue
                color_image = frame_to_bgr_image(color_frame)
                if color_image is None:
                    print("failed to convert frame to image")
                    continue
                
                # cv2.imshow("Infrared Viewer", ir_image)
                self.hfile.write(color_image)
                # if int(round(time.time())) -self.t > 30:
                #     self.flag = 'stop'
            else:
                time.sleep(0.01)

class CameraRecorder(threading.Thread):
    def __init__(self, name, param):
        threading.Thread.__init__(self, name=name)
        self.param = param
        self.isrun = False
        self.hfile = None
        self.camera = None
        self.t = int(round(time.time()))
    
    def run(self):
        while True:
            global flag
            if flag == 'start' and self.isrun is False:
                self.camera = cv2.VideoCapture(0)
                self.camera.set(cv2.CAP_PROP_SETTINGS, 1)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                frame_size = (
                int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                frame_fps = 20
                video_format = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
                self.hfile = cv2.VideoWriter()
                filepath = self.param[:-4] + '_' + str(int(round(time.time() * 1000))) + self.param[-4:]
                self.hfile.open(filepath, video_format, self.camera.get(cv2.CAP_PROP_FPS), frame_size)
                self.isrun = True
            
            elif flag == 'stop':
                self.isrun = False
                self.hfile.release()
                self.camera.release()
                print('Thread finished.')
                return
            
            if self.isrun:
                sucess, video_frame = self.camera.read()
                self.hfile.write(video_frame)
                # if int(round(time.time())) -self.t > 30:
                #     self.flag = 'stop'
            else:
                time.sleep(0.1)

# Show image. Input parameter item is a dict, it contains keys 'filename', 'lasttime'
def ShowImg(win, item):
    filename = item['filename']
    
    if 'waitkey' in item.keys():
        pressed = False
        wait_keys = item['waitkey']

        pic = visual.ImageStim(win)
        pic.image = filename
        pic.draw()
        win.flip()

        # while not pressed:
        k = event.waitKeys(keyList=wait_keys)
        core.wait(1)
        return k[0]
    else:
        lasttime = item['lasttime']
        while lasttime > 0:
            pic = visual.ImageStim(win)
            pic.image = filename
            pic.draw()
            win.flip()
            core.wait(1)
            lasttime = lasttime - 1
        core.wait(1)


# Play movie. Input parameter item is a dict, it contains keys 'filename'
# You can pause/play(continue) the movie by pressing space key
def PlayMov(win, item):
    filename = item['filename']
    mov = visual.MovieStim3(win, filename)

    s1 = np.array([720, 576])
    s2 = np.array([380, 480])
    
    if (mov.size == s1).all():
        mov.size = (1200, 960)
    elif (mov.size == s2).all():
        mov.size = (760, 960)
    else:
        mov.size = (1706, 960)
        # mov.size = (1920,1080)
    
    
    
    play = True
    # play
    while mov.status != visual.FINISHED:
        if play == True:
            mov.draw()
            win.flip()
        else:
            core.wait(0.5)
        # response = event.getKeys()
        # if 'escape' in response:
        #     DebugInfo('Press escape key')
        #     if play:
        #         mov.pause()
        #         play = False
        # if 'space' in response:
        #     DebugInfo('Press space key')
        #     if play:
        #         mov.pause()
        #         play = False
        #     else:
        #         mov.play()
        #         play = True
            
def ShowText(win, item):
    strText = item['text']
    lasttime = item['lasttime']
    height = 30 #default height
    font='Hei' #default font
    position = (0.0, 0.0)#default position
    color = 'white'
    
    if 'textheight' in item.keys():
        height = item['textheight']
        
    if 'font' in item.keys():
        font = item['font']
        
    if 'position' in item.keys():
        position = item['position']
    
    if 'color' in item.keys():
        color = item['color']
        
    # text_instru = visual.TextStim(win, text=u'', height=height, font=font, pos=position, color=color)
    text_instru = visual.TextStim(win, text=u'', color=color)
    text_instru.text=strText
    text_instru.draw()
    win.flip()
    event.waitKeys(keyList=['escape'], maxWait=lasttime)
    

def ShowQuestionnaire(win, emos, ticks=[1,2,3,4,5,6,7,8,9], labels = None, fix_index=1, instructions='请根据您当前的情绪状态，对每一种情绪强度、视频\n熟悉和喜爱程度打分。1表示一点都没有，9表示非常强:'):
    if labels is None:
        labels = ticks
    
    rt = RatingPage(win, emos, ticks=ticks, labels=labels, fix_indx=fix_index, instructions=instructions)

    event.clearEvents()  # 清除之前的event事件。
    button = visual.Rect(win, width=0.2, height=0.11,
                         fillColor='gray',
                         pos=(0.8, -0.8))  # 用visual.Rect建了一个0.2*0.11的矩形。
    text = visual.TextStim(win, text='Next',
                           height=0.1,
                           color='black',
                           pos=(0.8, -0.8))  # 位置与button相同。
    myMouse = event.Mouse()
    
    while not myMouse.isPressedIn(button) or not rt.isReady():
        if rt.isReady():
            button.fillColor = 'White'
            if button.contains(myMouse):
                button.opacity = 0.8
            else:
                button.opacity = 0.5
        else:
            button.fillColor = 'gray'
            
        rt.draw()
        button.draw()
        text.draw()
        win.flip()
        # core.wait(1)
    return rt.getRating()


def ShowQuestionnaire_I(win, emos, img, ticks=[1, 2, 3, 4, 5, 6, 7, 8, 9], labels=None, fix_index=1,
                      instructions=''):
    if labels is None:
        labels = ticks
    
    rt = ImgRatingPage(win, emos, img=img, ticks=ticks, labels=labels, fix_indx=fix_index, instructions=instructions)
    
    event.clearEvents()  # 清除之前的event事件。
    button = visual.Rect(win, width=0.2, height=0.11,
                         fillColor='gray',
                         pos=(0.8, -0.8))  # 用visual.Rect建了一个0.2*0.11的矩形。
    text = visual.TextStim(win, text='Next',
                           height=0.1,
                           color='black',
                           pos=(0.8, -0.8))  # 位置与button相同。
    myMouse = event.Mouse()
    
    while not myMouse.isPressedIn(button) or not rt.isReady():
        if rt.isReady():
            button.fillColor = 'White'
            if button.contains(myMouse):
                button.opacity = 0.8
            else:
                button.opacity = 0.5
        else:
            button.fillColor = 'gray'
        
        rt.draw()
        button.draw()
        text.draw()
        win.flip()
        # core.wait(1)
    return rt.getRating()

class EEGTrigger():
    def __init__(self, serial_port=SERIAL_PORT):
        self.triggerin = TriggerIn(serial_port)
        if not self.triggerin.validate_device():
            raise Exception('Invalid Serial!')

    def send(self, trigger):
        self.triggerin.output_event_data(trigger)


def SendEegMarker(marker):
    global triggerObj
    triggerObj.send(marker)
    print("send trigger")
        


# vid, marker : -1  0开启视频录制, -1 1结束录制
# vid=30 练习视频
def SendMarker(vid, marker, eeg=True):
    # marker for camera
    video_pinfo = open(os.path.join(rootpath, 'subjects', str(sub_no), 'camera.csv'), 'a', newline='')
    writer = csv.writer(video_pinfo)
    row = (vid, marker, int(round(time.time()*1000)))
    writer.writerow(row)
    video_pinfo.close()

    if eeg:
        # for eeg equipment
        # global triggerObj
        # triggerObj.send(marker)
        SendEegMarker(marker)


# PANAS 测试

def DiscreteEmos(win, rootpath, info1, vid, practice=False, ticks=[1,2,3,4,5,6,7,8,9]):
    emos = [u'娱乐(Amusement)', u'愤怒(Anger)', u'厌恶(Disgust)', u'恐惧(Fear)', u'喜悦(Joy)', u'悲伤(Sadness)',
            u'温柔(Tenderness)', u'熟悉度(Familiarity)', u'喜欢度(Liking)']
    # emos_en = {u'娱乐': 'Amusement', u'愤怒': 'Anger', u'厌恶': 'Disgust', u'恐惧': 'Fear',
    #            u'喜悦': 'Joy', u'悲伤': 'Sadness', u'温柔': 'Tenderness'}
    emo_instr = '请根据您当前的情绪状态，对每一种情绪强度、视频\n熟悉和喜爱程度打分。1表示一点都没有，9表示非常强:'
    
    
    if not practice:
        dataFile1 = open(os.path.join(rootpath, 'subjects', info1['No'], "%s_emotions.csv" % (
                    info1['No'] + '_' + info1['Time'] + '_' + info1['Name'] + '_' + info1['Age'] + '_' + info1['Gender'] + '_' + info1['Handedness'])), 'a', newline='')
        writer = csv.writer(dataFile1)

    scores = (vid, ) #格式为vid+每个词的评分

    rts = ShowQuestionnaire(win, emos, fix_index=-2,
                            instructions=emo_instr, ticks=ticks)  # , './pics/ch/scales4panas-bg.png', emos_en=adj_en)
    for k in emos:
        scores = scores + (rts[k],)

    if not practice:
        writer.writerow(scores)
        dataFile1.close()
    
    if practice:
        return rts

def Adjective(win, rootpath, info1, vid, practice=False, ticks=[1,2,3,4,5]):
    
    adj = [u'受鼓舞的(Inspired)', u'警觉的(Alert)', u'兴奋的(Excited)', u'热情的(Enthusiastic)', u'坚定的(Determinded)', u'害怕的(Afraid)', u'难过的(Upset)', u'焦虑的(Nervous)', u'惊恐的(Scared)', u'苦恼的(Distressed)']
    # adj_en = {u'受鼓舞的':'Inspired', u'警觉的':'Alert', u'兴奋的':'Excited', u'热情的':'Enthusiastic', u'坚定的':'Determinded',
    #           u'害怕的':'Afraid', u'难过的':'Upset', u'焦虑的':'Nervous', u'惊恐的':'Scared', u'苦恼的':'Distressed'}

    trialNumber = list(range(len(adj)))
    random.shuffle(trialNumber)
    
    if not practice:
        dataFile1 = open(os.path.join(rootpath, 'subjects', info1['No'], "%s_panas.csv" % (
                    info1['No'] + '_' + info1['Time'] + '_' + info1['Name'] + '_' + info1['Age'] + '_' + info1['Gender'] + '_' + info1['Handedness'])), 'a', newline='')
        writer = csv.writer(dataFile1)

    scores = (vid, ) #格式为vid+每个词的评分

    adj_t = adj.copy()
    rts = ShowQuestionnaire(win, adj_t, ticks=ticks, instructions='请根据自己当前的情绪状态对每个情绪词进行评分，\n1表示一点都没有，5表示非常强:', fix_index=0)
    for k in adj:
        scores = scores + (rts[k],)

    if not practice:
        writer.writerow(scores)
        dataFile1.close()
    
    
    return 0


# 加减法计算
def Caluate(win, df):
    trialNumber = np.array([])
    times = int(len(df) / 4)
    for i in range(4):
        num = range(0, times)  # 范围在0到times之间，需要用到range()函数。
        nums = random.sample(num, 3)  # 加法正确 加法错误 减法正确 减法错误 分别选取三个算式
        nums = np.array(nums) + i * times
        trialNumber = np.hstack((trialNumber, nums))
    
    random.shuffle(trialNumber)
    
    correctNum = 0
    
    for trial_ in trialNumber:
        trial = int(trial_)
        # current_time = timer.getTime()
        text_formula = visual.TextStim(win, text=u'', font='Hei', pos=(0, 0), color='white')
        text_formula.text = str(df.iloc[trial][0]) + ' ' + str(df.iloc[trial][1]) + ' ' + str(
            df.iloc[trial][2]) + ' = ' + str(df.iloc[trial][4])
        # operation text
        text_instruction = visual.TextStim(win, text=u'【1】正确 【2】错误', pos=(0.0, -0.3), color='White')
        text_formula.draw()
        text_instruction.draw()
        win.flip()
        # core.wait(4)
        
        K_reaction = event.waitKeys(keyList=['escape', '1', '2'], maxWait=4)
        if not K_reaction:  # 没有按键动作
            continue
        if ('escape' in K_reaction):
            return 0
        opA = int(df.iloc[trial][0])
        opB = int(df.iloc[trial][2])
        opC = int(df.iloc[trial][4])
        # strRet = u'错误'
        if str(df.iloc[trial][1]) == '+':
            if ((opA + opB) == opC and K_reaction[0] == '1') or ((opA + opB) != opC and K_reaction[0] == '2'):
                correctNum = correctNum+1
                # strRet = u'正确'
        if str(df.iloc[trial][1]) == '-':
            if ((opA - opB) == opC and K_reaction[0] == '1') or ((opA - opB) != opC and K_reaction[0] == '2'):
                correctNum = correctNum+1
                # strRet = u'正确'
            
        # elif('a' in K_reaction or 's' in K_reaction):
        #     K_reaction2 = event.waitKeys(keyList=['1','2'], maxWait=4)
        else:
            pass
        # ShowText(win, {'text': strRet, 'lasttime': 0.5})
    
    DebugInfo("Accuracy:"+str(correctNum/len(trialNumber)))
    return correctNum/len(trialNumber)


def WriteRow(file, row, mode='a'):
    fHandle = open(file, mode, newline='')
    writer = csv.writer(fHandle)
    writer.writerow(row)
    fHandle.close()


def MainProcess():
    # collect subject's information
    info = {'Name': '', 'Age': '', 'Gender': ['M', 'F'], 'No': '', 'Handedness': ['Right', 'Left', 'Both'],
            'Time': ['Pre', 'Post']}
    infoDlg = gui.DlgFromDict(dictionary=info, title=u'基本信息-多模态心理状态分析',
                              order=['No', 'Time', 'Name', 'Age', 'Gender', 'Handedness'])
    if infoDlg.OK == False:
        DebugInfo('Subject cancel the experiment.')
        core.quit()

    if os.path.exists(os.path.join(rootpath, 'subjects', info['No'])):
        print('Subject ' + str(info['No']) + ' exists.')
        core.quit()

    # 被试ID
    global sub_no
    sub_no = info['No']
    # 加载加减法题目
    df = pd.read_excel('pracComputeQuestion.xlsx', header=None)
    # create the main window
    scnWidth, scnHeight = [1920, 1080]
    # win = visual.Window((scnWidth, scnHeight), fullscr=True, units='pix', color='black', colorSpace='rgb')
    win = visual.Window((scnWidth, scnHeight), fullscr=True, color='black', colorSpace='rgb')
    win.mouseVisible = False
    if not os.path.exists(os.path.join(rootpath, 'subjects',info['No'])):
        if not os.path.exists(os.path.join(rootpath, 'subjects')):
            os.mkdir(os.path.join(rootpath, 'subjects'))
        os.mkdir(os.path.join(rootpath, 'subjects', info['No']))
    # subject information
    dataFile = open(os.path.join(rootpath, 'subjects',info['No'], "%s.csv"%(info['No']+'_'+info['Time']+'_'+info['Name']+'_'+info['Age']+'_'+info['Gender']+'_'+info['Handedness'])), 'a')
    dataFile.write(info['No']+','+info['Time']+','+info['Name']+','+info['Age']+','+info['Gender']+','+info['Handedness'])
    dataFile.close()



    # prepare camera and mqtt client
    if not DEBUG:
        cam_thr_ir = IRCameraRecorder('IRCam1', os.path.join(rootpath, 'subjects', info['No'],'IR_1.mp4'))
        cam_thr_color = ColorCameraRecorder('ColorCam1', os.path.join(rootpath, 'subjects', info['No'],'COLOR_1.mp4'))
        cam_thr_ir.start()
        cam_thr_color.start()
        StartCamera()
        mqtt = MQTT(filepath=os.path.join(rootpath, 'subjects', info['No']), HOST=HOST)
        mqtt.loop_start()


    # practice stage
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'practice_instructions.png'), 'waitkey': ['space']})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'Instructions-excerpt.png'), 'waitkey': ['space']})
    if not DEBUG:
        mqtt.setMarker(PRACTICE_VID + 10)
        SendMarker(PRACTICE_VID, PRACTICE_VID + 10)
    #play video
    PlayMov(win, {'filename': os.path.join(rootpath, 'videos', 'practice.mp4')})

    if not DEBUG:
        mqtt.setMarker(PRACTICE_VID + 100)
        SendMarker(PRACTICE_VID, PRACTICE_VID + 100)
    
    
    # PANAS
    ShowImg(win,
            {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'PANASInstruction-v3.png'), 'waitkey': ['space']})
    Adjective(win, rootpath, info, int(PRACTICE_VID), practice=True)
    
    # VAD
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'practice-arousal.png'), 'waitkey': ['space']})
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'ArousalPic.png'),
    #                             'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    rts = ShowQuestionnaire_I(win, ['Arousal'], './pics/' + LANG + '/ArousalPic.png')
    
    # ShowText(win, {'text': '+', 'lasttime': 1})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'practice-valence.png'), 'waitkey': ['space']})
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'ValencePic.png'),
    #                             'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    rts = ShowQuestionnaire_I(win, ['Valence'], './pics/' + LANG + '/ValencePic.png')
    
    # ShowText(win, {'text': '+', 'lasttime': 1})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'practice-dominance.png'), 'waitkey': ['space']})
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'Dominance.png'),
    #                               'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    rts = ShowQuestionnaire_I(win, ['Dominance'], './pics/' + LANG + '/Dominance.png')
    
    
    # Discrete emotions
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'DiscreteEmosInstruction.png'), 'waitkey': ['space']})
    DiscreteEmos(win, rootpath, info, int(PRACTICE_VID), practice=True)

    # math calculation
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'MathInstruction.png'), 'waitkey': ['space']})
    Caluate(win, df)

    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'practice-end.png'), 'waitkey': ['space']})



    # jingxi tai
    if not DEBUG:
        mqtt.setMarker(REST_VID + 10)
        SendMarker(REST_VID, REST_VID + 10)
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'reststate-instruction.png'), 'lasttime': 3})
    ShowText(win, {'text': '+', 'lasttime': RESTING_STATE_DUR})
    if not DEBUG:
        mqtt.setMarker(REST_VID + 100)
        SendMarker(REST_VID, REST_VID + 100)



    videos = ['Amusement-Just Another Pandora\'s Box.avi', 'Anger-City of Life and Death.avi', 'Disgust-Farewell My Concubine.avi',
              'Fear-The Chrysalis.avi', 'Joy-Better and Better.avi', 'Sadness-Changjiang Qihao.avi', 'Tenderness-A Simple Life.avi']


    videos_latin = np.array([
        [1, 2, 7, 3, 6, 4, 5],
        [2, 3, 1, 4, 7, 5, 6],
        [3, 4, 2, 5, 1, 6, 7],
        [4, 5, 3, 6, 2, 7, 1],
        [5, 6, 4, 7, 3, 1, 2],
        [6, 7, 5, 1, 4, 2, 3],
        [7, 1, 6, 2, 5, 3, 4]])



    # find the block corresponds to the subject number
    trialnums = videos_latin.shape[1]
    row_num = (int(info['No'])-1)%trialnums
    video_seq = videos_latin[row_num]

    # block loop
    for vid in video_seq:
        vid = vid-1
        # show instruction
        ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'Instructions-excerpt-auto.png'),
                      'lasttime': 3})
        
        # play video trigger
        if not DEBUG:
            mqtt.setMarker(vid + 10)
            SendMarker(vid, vid + 10)
        PlayMov(win, {'filename': os.path.join(rootpath, 'videos', videos[vid])})
        
        # video stop trigger
        if not DEBUG:
            mqtt.setMarker(vid + 100)
            SendMarker(vid, vid + 100)
        
        # Panas
        ShowImg(win,
                {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'PANASInstruction-auto.png'), 'lasttime': 3})
        Adjective(win, rootpath, info, int(vid))
        
        # Valence/Arousal/Dominant
        ShowImg(win,
                {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'Instructions-avd-auto.png'), 'lasttime': 3})
        # key_arousal = ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'ArousalPic.png'),
        #                             'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
        rts = ShowQuestionnaire_I(win, ['Arousal'], './pics/' + LANG + '/ArousalPic.png')
        Arousal_Val = rts['Arousal']
        
        ShowText(win, {'text': '+', 'lasttime': 1})
        # key_valence = ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'ValencePic.png'),
        #                             'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
        rts = ShowQuestionnaire_I(win, ['Valence'], './pics/' + LANG + '/ValencePic.png')
        Valence_Val = rts['Valence']
        
        ShowText(win, {'text': '+', 'lasttime': 1})
        # key_dominance = ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'Dominance.png'),
        #                               'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
        rts = ShowQuestionnaire_I(win, ['Dominance'], './pics/' + LANG + '/Dominance.png')
        Dominance_Val = rts['Dominance']
        
        WriteRow(os.path.join(rootpath, 'subjects', info['No'], 'Arousal_Valence.csv'),
                 [vid, int(Arousal_Val), int(Valence_Val), int(Dominance_Val)])
        
        # Discrete emotions
        ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'DiscreteEmosInstruction-auto.png'),
                      'lasttime': 3})
        DiscreteEmos(win, rootpath, info, int(vid))
        
        # rest
        ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'rest-5s.png'), 'lasttime': 5})

        if vid != video_seq[-1]:
            # math calculation
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'MathInstruction.png'), 'waitkey': ['space']})
            Caluate(win, df)
            # rest
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'rest-15s.png'), 'lasttime': 15})
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'goon.png'), 'waitkey': ['space']})


    # prepare for exiting
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics/'+LANG+'/', 'end.png'), 'lasttime': 10})
    # core.wait(10)
    if not DEBUG:
        mqtt.loop_stop()
        StopCamera()
        cam_thr_ir.join()
        cam_thr_color.join()

def CamTest():
    cam_thr_ir = IRCameraRecorder('IRCam1', os.path.join(rootpath, 'test_ir_1.mp4'))
    cam_thr_color = ColorCameraRecorder('ColorCam1', os.path.join(rootpath, 'test_color_1.mp4'))
    cam_thr_ir.start()
    cam_thr_color.start()
    global flag
    flag = 'start'
    core.wait(30)
    flag = 'stop'
    cam_thr_ir.join()
    cam_thr_color.join()
    print("finished")
    
    
def Main():
    scnWidth, scnHeight = [1920, 1080]
    win = visual.Window((scnWidth, scnHeight), fullscr=True, color='black', colorSpace='rgb')
    
    # VAD
    ShowImg(win,
            {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'practice-arousal.png'), 'waitkey': ['space']})
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'ArousalPic.png'),
    #               'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    rts = ShowQuestionnaire_I(win, ['Arousal'], './pics/'+LANG+'/ArousalPic.png')
    print(rts['Arousal'])
    
    # ShowText(win, {'text': '+', 'lasttime': 1})
    ShowImg(win,
            {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'practice-valence.png'), 'waitkey': ['space']})
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'ValencePic.png'),
                  # 'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    
    rts = ShowQuestionnaire_I(win, ['Valence'], './pics/' + LANG + '/ValencePic.png')
    print(rts['Valence'])
    
    # ShowText(win, {'text': '+', 'lasttime': 1})
    ShowImg(win,
            {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'practice-dominance.png'), 'waitkey': ['space']})
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'Dominance.png'),
    #               'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    
    rts = ShowQuestionnaire_I(win, ['Dominance'], './pics/' + LANG + '/Dominance.png')
    print(rts['Dominance'])
    
    # rts=ShowQuestionnaire_I(win,['Arousal'], './pics/ch/ArousalPic.png')
    # ShowImg(win, {'filename': os.path.join(rootpath, 'pics/' + LANG + '/', 'reststate-instruction.png'), 'lasttime': 3})
    # ShowText(win, {'text': '+', 'lasttime': RESTING_STATE_DUR})
    # rts=DiscreteEmos(win, rootpath, None, 0, True)
    
    
    # Adjective(win, rootpath, None, 1)
    
    

if __name__ == '__main__':
    # Main()
    # exit(0)

    InitGlobal()
    # #trigger test
    # for i in range(50):
    #     SendEegMarker(i)
    #     time.sleep(1)
    # core.quit()

    # #test of communication with wrist device 
    # mqtt = MQTT(filepath=os.path.join('./', 'subjects', '0'), HOST=HOST)
    # mqtt.loop_start()
    # core.wait(100)
    # core.quit()

    MainProcess()