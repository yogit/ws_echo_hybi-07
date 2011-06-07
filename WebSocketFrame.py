#!/usr/bin/env python
#-*- coding:utf8 -*-

class WebSocketFrame:
    """ ハンドシェイク後にサーバ・クライアント間で送受信されるフレームに関するクラス
    """

    def __init__(self, byteString):
        self.FIN  = True if ord(byteString[0]) & 0x80 else False
        self.RSV1 = True if ord(byteString[0]) & 0x40 else False
        self.RSV2 = True if ord(byteString[0]) & 0x20 else False
        self.RSV3 = True if ord(byteString[0]) & 0x10 else False
        self.opcode = ord(byteString[0]) & 0x0f
        self.MASK = True if ord(byteString[1]) & 0x80 else False
        self.payloadLen = ord(byteString[1]) & 0x7f
        maskingKeyPos = 2
        if self.payloadLen > 125:  # 拡張されたpayload lengthがある場合
            extendedPayloadLenPos = maskingKeyPos
            # 後に続く2バイトが拡張されたpayload lengthの場合
            if self.payloadLen == 126:
                maskingKeyPos += 2
            # 後に続く8バイトが拡張されたpayload lengthの場合
            elif self.payloadLen == 127:
                maskingKeyPos += 8
            self.payloadLen = self.bs2i(byteString[extendedPayloadLenPos:maskingKeyPos])
        if self.MASK:
            # 4バイトのMasking-keyを4つの数値に分ける
            payloadDataPos = maskingKeyPos + 4
            self.maskingKey = [ord(k) for k in byteString[maskingKeyPos:payloadDataPos]]
        else:  # 拡張されたpayload lengthがない場合
            payloadDataPos = maskingKeyPos
        self.payloadData = byteString[payloadDataPos:payloadDataPos+self.payloadLen]

    def bs2i(self, byteString):
        """ バイト文字列を整数値に変換するメソッド

        Arguments:
        - byteString: バイト文字列
        Returns:
        -num: 変換後の整数値
        """
        num = 0
        for c in byteString:
            num <<=8
            num |= ord(c)

        return num

    def getPayloadData(self):
        """ フレーム内のPayload Dataを取り出すメソッド

        opcodeの値を調べ、テキストフレームならMasking-keyの値を用いて
        マスクされたPayload Dataを正しいデータに戻す。バイナリフレーム
        に関しては未対応。

        Returns:
        -data: Payload Data
        """
        data = ''
        for i in range(len(self.payloadData)):
            data += chr(self.maskingKey[i%4] ^ ord(self.payloadData[i]))
        if self.opcode == 1:    # テキストフレームの場合
            data = data.decode('utf8')
        elif self.opcode == 2:  # バイナリフレームの場合(未対応)
            pass

        return data

    def getStatusCode(self):
        """ クローズフレーム内のStatus Codeの値を取り出すメソッド

        Returns:
        - statusCode: ステータスコード
        """
        statusCode = self.bs2i(self.getPayloadData()[:2])
        return statusCode
