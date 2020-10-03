#! /usr/bin/python

#
# Qt example for VLC Python bindings
# Copyright (C) 2009-2010 the VideoLAN team
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston MA 02110-1301, USA.
#

import sys
import os.path
from PyQt5.QtCore import Qt, QTimer, QRect, QSize
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon, QFont
from PyQt5.QtWidgets import QMainWindow, QWidget, QFrame, QSlider, QHBoxLayout, QPushButton, \
    QVBoxLayout, QAction, QFileDialog, QApplication, \
    QLabel, QLineEdit, QCheckBox, QRadioButton, QListWidget, QListWidgetItem
import vlc

import time
import json
import pickle
import tqdm
import re
from urllib import request
import threading
import functools

# Function for Channel Mapping
def read_m3u(filepath):
    stream_db = []
    with open(filepath, encoding='UTF8') as f:
        stream_info = None
        extinf_pattern = re.compile('#EXTINF:[\-0-9]+(.*),(.*)$')
        attr_pattern = re.compile('tvg-id=\"([0-9]+)\" tvg-logo=\"([0-9A-Za-z.:/_?=]+)\" tvh-chnum=\"([0-9]+)\"')
        for line in f.readlines():
            if line.startswith('#EXTM3U'):
                pass
            elif line.startswith('#EXTINF'):
                m = extinf_pattern.match(line)
                attrs, ch_name = m.group(1), m.group(2)
                m = attr_pattern.match(attrs.strip())
                tvg_id = m.group(1) if m else  ""
                tvg_logo = m.group(2) if m else ""
                tvh_chnum = m.group(3) if m else ""
                stream_info = {
                    'tvg-id': tvg_id.strip(),
                    'tvg-logo': tvg_logo.strip(),
                    'tvh-chnum': tvh_chnum.strip(),
                    'ch-name': ch_name.strip(),
                }
            elif line.startswith('udp://'):
                stream_info['multicast'] = line.strip('\r\n')
                stream_db.append(stream_info)
        return stream_db

def remove_unmapped_channel(playlist, stream_urls):
    out = []
    for line in playlist:
        if line['multicast'] in stream_urls:
            out.append(line)
    return out

def fill_unmapped_channel(playlist, channels):
    mapped = dict([(_['tvg-id'], _) for _ in playlist])
    for service_id in channels:
        channel = channels[service_id]
        stream_info = {
            'tvg-id': channel['ServiceId'],
            'tvg-logo': channel['Icon_url'],
            'tvh-chnum': channel['SKBCh'],
            'ch-name': channel['SKB Name'],
        }
        if service_id in mapped:
            mapped[service_id].update(stream_info)
        else:
            stream_info['multicast'] = None
            playlist.append(stream_info)
    return playlist

# VLC Error Check
vlc_error_count = 0
vlc_error_check = False
vlc_handle_mode = 0
@vlc.CallbackDecorators.LogCb
def vlc_log_callback(data, level, ctx, fmt, args):
    global vlc_error_count, vlc_error_check, vlc_handle_mode
    if level >= 3: vlc_error_count += 1
    if vlc_error_count > 500 and vlc_error_check == False:
        vlc_error_check = True
        if vlc_handle_mode != 0:
            player.disableChannel()
            print('Disabled Channel')

if len(sys.argv) < 3:
    print('$ python %s [Recent Scanned M3U] [Used M3U]' % sys.argv[0])
    print('# M3U can be make by MCTV Playlist Creator')
    print('# SKBroadband Multicast Range : 239.192.38.1-239.192.150.254 [49220]')
    sys.exit(1)

class Player(QMainWindow):
    """A simple Media Player using VLC and Qt
    """
    def __init__(self, master=None):
        # Read Data
        with open('channels.json', encoding='UTF8') as f:
            channels = dict([(_['ServiceId'], _) for _ in json.loads(f.read())])
        new_stream_db = read_m3u(sys.argv[1])
        old_stream_db = read_m3u(sys.argv[2])

        stream_urls = [_['multicast'] for _ in new_stream_db]

        if os.path.exists('.cache'):
            with open('.cache', 'rb') as f:
                cache = pickle.loads(f.read())
        else:
            cache = {}

        # Checking broken stream
        global vlc_error_count, vlc_error_check, vlc_handle_mode
        instance = vlc.Instance("--verbose=-1")
        instance.log_set(vlc_log_callback, None)
        mediaplayer = instance.media_player_new()
        mediaplayer.video_set_scale(0.1)
        print('Checking broken stream...')
        for url in tqdm.tqdm(stream_urls):
            if not url in cache:
                vlc_error_count = 0
                vlc_error_check = False
                mediaplayer.set_media(instance.media_new(url))
                mediaplayer.play()
                time.sleep(3)
                cache[url] = vlc_error_check
            with open('.cache', 'wb') as f:
                f.write(pickle.dumps(cache))
        mediaplayer.stop()
        self.stream_verify = cache
        vlc_handle_mode = 1
        ##############################

        playlist = remove_unmapped_channel(old_stream_db, stream_urls)
        playlist = fill_unmapped_channel(playlist, channels)

        self.channel_info = channels
        self.playlist = playlist
        self.stream_urls = stream_urls

        import pprint
        #pprint.pprint(update_db)
        print(len(old_stream_db), len(playlist), len(new_stream_db), len(channels))

        # QT Initialize
        QMainWindow.__init__(self, master)
        self.setWindowTitle("Media Player")

        # creating a basic vlc instance
        self.instance = vlc.Instance("--verbose=-1")
        self.instance.log_set(vlc_log_callback, None)
        # creating an empty vlc media player
        self.mediaplayer = self.instance.media_player_new()

        self.createUI()

    def createUI(self):
        """Set up the user interface, signals & slots
        """
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        # In this widget, the video will be drawn
        if sys.platform == "darwin": # for MacOS
            from PyQt5.QtWidgets import QMacCocoaViewContainer	
            self.videoframe = QMacCocoaViewContainer(0)
        else:
            self.videoframe = QFrame()
        self.palette = self.videoframe.palette()
        self.palette.setColor (QPalette.Window, QColor(0,0,0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)
        self.videoframe.setMinimumWidth(720)
        self.videoframe.setMinimumHeight(480)

        #self.hbuttonbox = QHBoxLayout()
        #self.openchannel = QPushButton("Open Channel Data")
        #self.hbuttonbox.addWidget(self.openchannel)
        #self.openchannel.clicked.connect(self.PlayPause)

        self.hcontrolbox = QHBoxLayout()
        self.hinfobox = QHBoxLayout()
        self.icon = QLabel()
        self.icon.setFixedSize(200, 60)
        self.icon.setAlignment(Qt.AlignCenter)
        self.hinfobox.addWidget(self.icon)
        self.vinfobox = QVBoxLayout()
        self.ch_name = QLabel("Loading...")
        font = QFont()
        font.setBold(True)
        font.setFamily('Malgun Gothic')
        font.setPointSize(16)
        self.ch_name.setFont(font)
        self.vinfobox.addWidget(self.ch_name)
        self.hservicebox = QHBoxLayout()
        self.hservicebox.addWidget(QLabel('Service ID '))
        self.service_id = QLabel("[#]")
        self.hservicebox.addWidget(self.service_id)
        self.vinfobox.addLayout(self.hservicebox)
        self.hinfobox.addLayout(self.vinfobox)
        self.hcontrolbox.addLayout(self.hinfobox)

        self.hcontrolbox.addStretch(1)
        self.volumeslider = QSlider(Qt.Horizontal, self)
        self.volumeslider.setMaximum(100)
        self.volumeslider.setValue(self.mediaplayer.audio_get_volume())
        self.volumeslider.setToolTip("Volume")
        self.hcontrolbox.addWidget(self.volumeslider)
        self.volumeslider.valueChanged.connect(self.setVolume)

        #
        self.channelbox = QVBoxLayout()
        self.channellist = QListWidget()
        self.channellist.setFixedWidth(320)
        self.channellist.itemClicked.connect(self.selectChannel)
        self.channelbox.addWidget(self.channellist)
        self.channelfilter = QLineEdit()
        self.channelfilter.setFixedWidth(320)
        self.channelfilter.textChanged.connect(self.find_channel)
        self.channelbox.addWidget(self.channelfilter)
        
        self.streambox = QVBoxLayout()
        self.streamlist = QListWidget()
        self.streamlist.setFixedWidth(320)
        self.streamlist.itemClicked.connect(self.selectStream)
        self.streambox.addWidget(self.streamlist)
        self.mapbutton = QPushButton("Map")
        self.mapbutton.clicked.connect(self.map)
        self.streambox.addWidget(self.mapbutton)

        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe)
        self.vboxlayout.addLayout(self.hcontrolbox)

        self.hboxlayout = QHBoxLayout()
        self.hboxlayout.addLayout(self.vboxlayout)
        self.hboxlayout.addLayout(self.channelbox)
        self.hboxlayout.addLayout(self.streambox)

        self.widget.setLayout(self.hboxlayout)

        save = QAction("&Save", self)
        save.triggered.connect(self.SaveFile)
        exit = QAction("&Exit", self)
        exit.triggered.connect(sys.exit)
        menubar = self.menuBar()
        filemenu = menubar.addMenu("&File")
        filemenu.addAction(save)
        filemenu.addSeparator()
        filemenu.addAction(exit)

        self.updatePlaylist()

    def SaveFile(self):
        print(os.path.expanduser('~'))
        #filename = QFileDialog.getSaveFileName(self, "Save File", os.path.expanduser('~'),)[0]
        filename = QFileDialog.getSaveFileName(self, "Save File", filter="M3U Playlist (*.m3u *.m3u8)",)[0]
        print(filename)

        with open(filename, 'wt', encoding='UTF8') as f:
            f.write('#EXTM3U\n')
            for item in [self.channellist.item(_) for _ in range(self.channellist.count())]:
                if item.checkState():
                    data = item.data(Qt.UserRole)
                    f.write(f"#EXTINF:-1 tvg-id=\"{data['tvg-id']}\" tvg-logo=\"{data['tvg-logo']}\" tvh-chnum=\"{data['tvh-chnum']}\", {data['ch-name']}\n")
                    f.write(f"{data['multicast']}\n")

    def setVolume(self, Volume):
        """Set the volume
        """
        self.mediaplayer.audio_set_volume(Volume)

    def find_channel(self, text):
        if text:
            for item in [self.channellist.item(_) for _ in range(self.channellist.count())]:
                if item.text().lower().find(text.lower()) >= 0:
                    item.setHidden(False)
                else:
                    item.setHidden(True)
        else:
            for item in [self.channellist.item(_) for _ in range(self.channellist.count())]:
                item.setHidden(False)

    def map(self, *args, **kwargs):
        item = self.channellist.currentItem()
        item.setCheckState(Qt.Checked)
        channel = item.data(Qt.UserRole)
        sitem = self.streamlist.currentItem()
        radio = self.streamlist.itemWidget(sitem)
        channel['multicast'] = radio.text()
        item.setData(Qt.UserRole, channel)
        self.updateMappedInfo()

    def playStream(self, stream_url):
        global vlc_error_count, vlc_error_check
        vlc_error_count = 0
        vlc_error_check = False

        self.media = self.instance.media_new(stream_url)
        # put the media in the media player
        self.mediaplayer.set_media(self.media)

        # parse the metadata of the file
        self.media.parse()
        # set the title of the track as window title
        self.setWindowTitle(self.media.get_meta(0))

        # the media player has to be 'connected' to the QFrame
        # (otherwise a video would be displayed in it's own window)
        # this is platform specific!
        # you have to give the id of the QFrame (or similar object) to
        # vlc, different platforms have different functions for this
        if sys.platform.startswith('linux'): # for Linux using the X Server
            self.mediaplayer.set_xwindow(self.videoframe.winId())
        elif sys.platform == "win32": # for Windows
            self.mediaplayer.set_hwnd(self.videoframe.winId())
        elif sys.platform == "darwin": # for MacOS
            self.mediaplayer.set_nsobject(int(self.videoframe.winId()))

        self.mediaplayer.play()

    def selectChannel(self, item):
        global vlc_error_count, vlc_error_check
        vlc_error_count = 0
        vlc_error_check = False

        channel = item.data(Qt.UserRole)
        print(channel)
        if 'multicast' in channel and channel['multicast']:
            streams = dict([(item.data(Qt.UserRole), item) for item in [self.streamlist.item(_) for _ in range(self.streamlist.count())]])
            if channel['multicast'] in streams:
                self.selectStream(streams[channel['multicast']])
            else:
                item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Unchecked)

        self.ch_name.setText(channel['ch-name'])
        frame = self.getIcon(channel['tvg-logo'])
        pixmap = QPixmap()
        pixmap.loadFromData(frame)
        self.icon.setPixmap(pixmap.scaled(self.icon.width(), self.icon.height(), Qt.KeepAspectRatio))
        self.service_id.setText(f"[{channel['tvg-id']}]")

    def updateStreamRadioState(self, state):
        if state: 
            found = False
            for item in [self.streamlist.item(_) for _ in range(self.streamlist.count())]:
                radio = self.streamlist.itemWidget(item)
                if radio.isChecked():
                    self.channellist.currentItem().setCheckState(Qt.Checked)
                    item.setText("")
                    self.streamlist.setCurrentItem(item)
                    self.streamlist.update(self.streamlist.currentIndex())
                    self.selectStreamImpl(item)
                    found = True
                    break
            if not found:
                item = self.streamlist.item(0)
                self.streamlist.setCurrentItem(item)
                self.selectStreamImpl(item)

    def selectStream(self, item):
        stream_info = item.data(Qt.UserRole)
        radio = self.streamlist.itemWidget(item)
        radio.setChecked(True)

    def selectStreamImpl(self, item):
        global vlc_error_count, vlc_error_check
        vlc_error_count = 0
        vlc_error_check = False

        radio = self.streamlist.itemWidget(item)
        url = radio.text()
        item.setData(Qt.UserRole, url)
        print('URL from Radio :', url)

        if url: 
            self.playStream(url)
            #citem = self.channellist.currentItem()
            #data = citem.data(Qt.UserRole)
            #data['multicast'] = url
            #citem.setData(Qt.UserRole, data)
            #print('Saved URL :', url)
        else: 
            pass
            #self.mediaplayer.pause()
            #citem = self.channellist.currentItem()
            #data = citem.data(Qt.UserRole)
            #data['multicast'] = None
            #citem.setData(Qt.UserRole, data)
            #print('Saved URL :', None)
        self.updateMappedInfo()

    def getMappedDict(self):
        mapped_dict = {}
        for item in [self.channellist.item(_) for _ in range(self.channellist.count())]:
            data = item.data(Qt.UserRole)
            if data['multicast']:
                if data['multicast'] in mapped_dict:
                    mapped_dict[data['multicast']].append(data['ch-name'])
                else:
                    mapped_dict[data['multicast']] = [data['ch-name']]
        return mapped_dict

    def updateMappedInfo(self):
        print('UpdateMappedInfo')
        mapped_dict = self.getMappedDict()
        for item in [self.streamlist.item(_) for _ in range(self.streamlist.count())]:
            url = item.data(Qt.UserRole)
            if url == '__BROKEN__':
                item.setText("*** BROKEN ***")
            elif url in mapped_dict:
                item.setText(f"[{','.join(mapped_dict[url])}]" if mapped_dict[url] else "")
            else:
                item.setText("")
            self.streamlist.update(self.streamlist.indexFromItem(item))

    def disableChannel(self):
        self.channellist.currentItem().setCheckState(Qt.Unchecked)
        self.channellist.update(self.channellist.currentIndex())
        data = self.channellist.currentItem().data(Qt.UserRole)
        data['multicast'] = None
        self.channellist.currentItem().setData(Qt.UserRole, data)

        self.streamlist.update(self.streamlist.currentIndex())
        self.streamlist.currentItem().setData(Qt.UserRole, '__BROKEN__')

        self.updateMappedInfo()
        #app.processEvents()

    @functools.lru_cache(maxsize=None)
    def getIcon(self, url):
        req = request.Request(url)
        req.add_header('User-Agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0')
        frame = None 
        for _ in range(3):
            try:
                resp = request.urlopen(req)
                frame = resp.read()
                break
            except:
                time.sleep(1)
        return frame

    def attachIcon(self, item):
        channel = item.data(Qt.UserRole)
        url = channel['tvg-logo']
        pixmap = QPixmap()
        pixmap.loadFromData(self.getIcon(url))
        item.setIcon(QIcon(pixmap))

    def asyncCacheIcon(self):
        def asyncThread(listwidget):
            for item in [listwidget.item(_) for _ in range(listwidget.count())]:
                channel = item.data(Qt.UserRole)
                self.attachIcon(item)
                listwidget.update(listwidget.indexFromItem(item))
        threading.Thread(target=asyncThread, args=(self.channellist,), daemon=True).start()

    def updatePlaylist(self):
        self.channellist.clear()
        for channel in self.playlist:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, channel)
            item.setText(f"[{channel['tvh-chnum']}] {channel['ch-name']}")
            item.setCheckState(Qt.Checked if channel['multicast'] and not self.stream_verify[channel['multicast']] else Qt.Unchecked)
            self.channellist.addItem(item)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, '')
        self.streamlist.addItem(item)
        radio = QRadioButton('Unbound Stream URL')
        radio.toggled.connect(self.updateStreamRadioState)
        self.streamlist.setItemWidget(item, radio)
        for url in self.stream_urls:
            item = QListWidgetItem()
            item.setTextAlignment(Qt.AlignRight)
            item.setData(Qt.UserRole, '__BROKEN__' if self.stream_verify[url] else url)
            self.streamlist.addItem(item)
            radio = QRadioButton(url)
            radio.toggled.connect(self.updateStreamRadioState)
            self.streamlist.setItemWidget(item, radio)

        self.updateMappedInfo()
        self.asyncCacheIcon()

        def delayedSelectChannel(n):
            time.sleep(n)
            self.channellist.setCurrentRow(0)
            self.selectChannel(self.channellist.currentItem())
        threading.Thread(target=delayedSelectChannel, args=(3,), daemon=True).start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Player()
    player.show()
    player.resize(720, 480)
    sys.exit(app.exec_())
