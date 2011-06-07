#!/usr/bin/env python
#-*- coding: utf8 -*-

import SocketServer
import base64
import hashlib
import threading
from datetime import datetime
from WebSocketFrame import WebSocketFrame

class TCPHandler(SocketServer.BaseRequestHandler):

    def setup(self):
        """ 初期化処理を行うメソッド

        SocketServer.BaseRequestHandlerのsetup()メソッドを上書きする。
        handle()メソッドより前に呼び出される。
        """
        self.configObj = {
            'host': '',
            'port': self.server.server_address[1],
            'resource': '/',
            'origin': '',      # 何も指定しなければすべてのoriginを許可する
            'protocol': [''],
            #'protocol': ['video', 'talk', 'chat'],  # 複数のサブプロトコルをサポートする場合
            'pingInterval': 0  # pingする間隔(単位：秒)。0ならpingしない
        }
        self.ishandshake = False
        self.frameObj = None
        self.totalPayloadDataNum = 0
        self.isreceiving = False
        self.pingTimerObj = None

    def handle(self):
        """ ハンドシェイクデータの送受信やフレームの送受信などを行うメソッド

        SocketServer.BaseRequestHandlerのhandle()メソッドを上書きする。setup()
        メソッドの後に呼び出される。
        """
        while True:
            receivedFrame = self.request.recv(10240)
            if not self.ishandshake:  # まだハンドシェイクしていない場合
                result = self.checkHandshake(receivedFrame)
                if result:  # 受信したハンドシェイクデータが適切だった場合
                    self.sendHandshake(result)
                    self.ishandshake = True
                    self.log('ハンドシェイクに成功')
                    if self.configObj['pingInterval']:  # pingするように設定されていた場合
                        threading.Thread(target=self.sendPing).start()
                else:       # 受信したハンドシェイクデータが不適切だった場合
                    self.log('ハンドシェイクに失敗')
                    break
            elif not self.isreceiving:  # ハンドシェイク済みでフレーム受信途中ではない場合
                self.frameObj = WebSocketFrame(receivedFrame)
                if not self.frameObj.FIN: print '断片化されたフレームの処理は未実装です'
                if self.frameObj.opcode == 0x8:    # クローズフレームを受信した場合
                    statusCode = self.frameObj.getStatusCode()
                    self.log('クローズフレーム(%d)を受信' % statusCode)
                    self.sendCloseFrame(statusCode)
                    break
                elif self.frameObj.opcode == 0x9:  # Pingメッセージを受信した場合
                    receivedData = self.frameObj.getPayloadData()
                    self.log('Pingメッセージ: ' + receivedData)
                    self.sendPong(receivedData)
                    self.log('Pongメッセージを返信')
                elif self.frameObj.opcode == 0xa:  # Pongメッセージを受信した場合
                    receivedData = self.frameObj.getPayloadData()
                    self.log('Pongメッセージ: ' + receivedData)
                # フレームをすべて受け取った場合
                elif self.frameObj.payloadLen == len(self.frameObj.payloadData):
                    receivedData = self.frameObj.getPayloadData()
                    self.log(receivedData)
                    self.sendTextFrame(receivedData)
                # フレームすべてを受け取っていない場合
                elif self.frameObj.payloadLen > len(self.frameObj.payloadData):
                    self.isreceiving = True
                    self.totalPayloadDataNum = len(self.frameObj.payloadData)
            else:  # ハンドシェイク済みでフレーム受信途中の場合
                self.frameObj.payloadData += receivedFrame
                self.totalPayloadDataNum += len(receivedFrame)
                # まだ受信していないデータが残っているか調べる
                if self.totalPayloadDataNum < self.frameObj.payloadLen: continue
                # フレームすべてを受信した場合
                receivedData = self.frameObj.getPayloadData()
                self.log(receivedData)
                self.sendTextFrame(receivedData)
                self.totalPayloadDataNum = 0
                self.isreceiving = False

    def finish(self):
        """ 終了処理を行うメソッド

        SocketServer.BaseRequestHandlerのfinish()メソッドを上書きする。
        handle()メソッドが呼び出された後に呼び出されてクライアントとの
        ソケットを閉じる。
        """
        if self.pingTimerObj: self.pingTimerObj.cancel()
        self.request.close()
        self.log('接続を閉じました')

    def log(self, msg):
        """ ログを出力するメソッド

        時間とクライアントのIPアドレス、ポート番号、ログメッセージを出力する。

        Arguments:
        - msg: ログメッセージ
        """
        now = datetime.now().strftime('%H:%M:%S')
        print '[' + now + ']', self.client_address, msg

    def sendCloseFrame(self, statusCode):
        """ クローズフレームを送信するメソッド

        引数で受け取ったステータスコードの値を含むクローズフレームを作成して、
        クライアントに送信する。

        Arguments:
        - statusCode: ステータスコード
        """
        sendData  = chr(0x88)  # FINビットとクローズフレームを意味するopstatusCodeの値
        sendData += chr(0x02)  # ステータスコードの長さは2バイト
        s = '%04x' % statusCode
        for start in range(0, len(s), 2):
            sendData += chr(int(s[start:start+2], 16))
        self.request.send(sendData)

    def sendPing(self):
        """ Pingメッセージを送信するメソッド

        クライアントにPingメッセージを送信し、一定時間後に再び送信するように
        タイマーをセットする。
        """
        pingBody = 'PING'
        sendData  = chr(0x89)  # FINビットとPingメッセージを意味するopcodeの値
        sendData += chr(len(pingBody))
        sendData += pingBody
        self.log('Pingメッセージを送信')
        self.request.send(sendData)
        self.pingTimerObj = threading.Timer(self.configObj['pingInterval'], self.sendPing)
        self.pingTimerObj.start()

    def resetPingTimer(self):
        """ Pingメッセージ送信タイマーをリセットするメソッド

        もしタイマーオブジェクトがあればリセットする。
        """
        if self.pingTimerObj:
            self.pingTimerObj.cancel()
            self.pingTimerObj = threading.Timer(self.configObj['pingInterval'], self.sendPing)
            self.pingTimerObj.start()

    def sendPong(self, pingBody):
        """ Pongメッセージを送信するメソッド

        クライアントにPongメッセージを送信し、Pingメッセージ送信タイマーの
        リセットを試みる
        """
        sendData  = chr(0x8a)  # FINビットとPongメッセージを意味するopcodeの値
        sendData += chr(len(pingBody))
        sendData += pingBody   # PongメッセージのボディはPingメッセージのボディと同じ
        self.request.send(sendData)
        self.resetPingTimer()

    def sendTextFrame(self, data):
        """ クライアントにテキストフレームを送信するメソッド

        引数で受け取ったテキストメッセージを断片化せず、シングルフレームで
        送信し、Pingメッセージ送信タイマーのリセットを試みる。

        Arguments:
        - data: 送信するテキストメッセージ
        """
        byteData = data.encode('utf8')  # 送信するためバイト文字列に変換(次の行より先に行う)
        dataSize = len(byteData)        # 送信するデータのバイト数(文字数ではない)を調べる
        sendData = chr(0x81)            # FINビットとテキストフレームを意味するopcodeの値
        if dataSize <= 125:  # 拡張payload lengthが必要ない場合
            sendData += chr(dataSize)
        else:  # 拡張payload lengthが必要な場合
            if dataSize < 2**16:
                sendData += chr(126)
                s = '%04x' % dataSize
            elif dataSize < 2**63:
                sendData += chr(127)
                s = '%016x' % dataSize
            for start in range(0, len(s), 2):
                sendData += chr(int(s[start:start+2], 16))
        sendData += byteData
        self.request.send(sendData)
        self.resetPingTimer()

    def sendHandshake(self, obj):
        """ クライアントにハンドシェイクデータを送信するメソッド

        引数で受け取った値を元にハンドシェイクデータを作成して送信する。
        サーバハンドシェイクのSec-WebSocket-AcceptとSec-WebSocket-Protocol
        の値はクライアントハンドシェイクの中から得る。

        Arguments:
        - obj: サーバのハンドシェイクデータに必要な値の集まり
        """
        tmp = obj['key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
        accept = base64.b64encode(hashlib.sha1(tmp).digest())
        sendData  = 'HTTP/1.1 101 Switching Protocols\r\n'
        sendData += 'Upgrade: websocket\r\n'
        sendData += 'Connection: Upgrade\r\n'
        sendData += 'Sec-WebSocket-Accept: ' + accept + '\r\n'
        if obj['protocol']:
            sendData += 'Sec-WebSocket-Protocol: ' + obj['protocol'] + '\r\n'
        sendData += '\r\n'
        self.request.send(sendData)
        self.log('ハンドシェイクデータを送信\n' + sendData)

    def checkHandshake(self, rawData):
        """ クライントからのハンドシェイクデータが適切か調べるメソッド

        クライアントハンドシェイクデータを引数で受け取り、内容が不適切であれば
        Falseを返し、内容が適切であればサーバハンドシェイクデータに必要な値であ
        るSec-WebSocket-Keyの値と、サブプロトコルの値を返す。サブプロトコルの値
        はサーバで利用可能なものと一致するならそのプロトコルが選ばれる。

        Arguments:
        - rawData: クライアントハンドシェイクデータ
        Returns:
        - obj: 
        """
        # この2つの値はサーバのハンドシェイク送信時に利用する
        obj = {
            'key': None,
            'protocol': None
        }
        self.log('ハンドシェイクデータを受信\n' + rawData)
        listDatas = rawData.split('\r\n')
        firstLine = listDatas[0]
        if firstLine != 'GET %s HTTP/1.1' % self.configObj['resource']:
            return False
        headerFields = {}
        for data in listDatas[1:]:
            if len(data): k, v = data.split(': ')
            headerFields[k] = v
        if self.configObj['host'] and 'Host' in headerFields.keys():
            if headerFields['Host'] != self.configObj['host'] + self.configObj['port']:
                return False
        if 'Upgrade' in headerFields.keys():
            if headerFields['Upgrade'] != 'websocket':
                return False
        if 'Connection' in headerFields.keys():
            if not headerFields['Connection'].find('Upgrade'):
                return False
        if 'Sec-WebSocket-Key' in headerFields.keys():
            if len(base64.b64decode(headerFields['Sec-WebSocket-Key'])) != 16:
                return False
        obj['key'] = headerFields['Sec-WebSocket-Key']
        if self.configObj['origin'] and 'Sec-WebSocket-Origin' in headerFields.keys():
            if self.configObj['origin'] != headerFields['Sec-WebSocket-Origin']:
                return False
        if 'Sec-WebSocket-Version' in headerFields.keys():
            if headerFields['Sec-WebSocket-Version'] != '7':
                return False
        if 'Sec-WebSocket-Protocol' in headerFields.keys() and self.configObj['protocol']:
            for p in headerFields['Sec-WebSocket-Protocol'].split(', '):
                if p in self.configObj['protocol']:
                    obj['protocol'] = p
                    break
        if 'Sec-WebSocket-Extensions' in headerFields.keys():
            pass
        
        return obj


if __name__ == '__main__':
    PORT = 8080
    SocketServer.ThreadingTCPServer.allow_reuse_address = True
    server = SocketServer.ThreadingTCPServer(('', PORT), TCPHandler)
    print '接続済みのクライアントがいないければCtrl+cで終了します'
    server.serve_forever()
