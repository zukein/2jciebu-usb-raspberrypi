import serial
import threading
import time
import ambient
import os
from datetime import datetime

class EnvSensor(threading.Thread):

    def __init__(self, port='/dev/ttyUSB0', interval=1):
        super(EnvSensor, self).__init__()
        # スレッドの実行/停止を判断するフラグ
        self.stop = False
        # スレッドのループ毎の待機時間
        self.interval = interval
        # USBセンサとのシリアル通信の初期化
        self.ser = serial.Serial(
            port,
            115200,
            serial.EIGHTBITS,
            serial.PARITY_NONE
        )
        # 各センサー値を格納する変数
        self.co2 = None
        self.temp = None

    def run(self):
        """
            runメソッドは、このオブジェクトがスレッドとして
            実行される際のメインループです
        """
        while not self.stop:
            # 最新データの取得
            data = self._get_latest_short()
            # このオブジェクトを利用するプログラムのために、
            # 取得したデータを元にインスタンス変数を更新します
            self._update(data)
            # インターバルに指定された時間だけ待機します
            time.sleep(self.interval)
            
        # スレッドの停止処理が行われた場合、シリアルポートを閉じます
        self._close()     

    def _get_latest_short(self):
        """
            最新のセンサーデータを`latest_short`フォーマット
            で取得します。詳しくはユーザーマニュアルの77pを
            参照してください

            https://omronfs.omron.com/ja_JP/ecb/products/pdf/CDSC-016A-web1.pdf
        """
        command = bytearray([0x52, 0x42, 0x05, 0x00, 0x01, 0x22, 0x50])
        command = command + self._calc_crc(command,len(command))
        tmp = self.ser.write(command)
        time.sleep(1)   
        return self.ser.read(30)

    def _update(self, data):
        """
            センサー値格納用のインスタンス変数を更新します
        """
        self.co2 = int(hex(data[23])+format(data[22], 'x'), 16)
        self.temp = int(hex(data[9])+format(data[8], 'x'), 16)/100

    def _calc_crc(self, buf, length):
        """
            データの誤りを検出させるために、CRC演算を行います。
            演算方法の詳細はユーザーマニュアルの68pを参照してください

            https://omronfs.omron.com/ja_JP/ecb/products/pdf/CDSC-016A-web1.pdf
        """
        crc = 0xFFFF
        for i in range(length):
            crc = crc ^ buf[i]
            for i in range(8):
                carrayFlag = crc & 1
                crc = crc >> 1
                if (carrayFlag == 1) : 
                    crc = crc ^ 0xA001
        crcH = crc >> 8
        crcL = crc & 0x00FF
        return(bytearray([crcL,crcH]))

    def _close(self):
        self.ser.close()

    def get_co2(self):
        return self.co2

    def get_temp(self):
        raise self.temp
    
    def get_humi(self):
        raise NotImplementedError()

    def stop(self):
        """
            スレッドを終了させます
        """
        self.stop = True

if __name__ == '__main__':
    try:
        CHANNEL_ID = int(os.environ['AMBIENT_CHANNEL_ID'])
        WRITE_KEY = os.environ['AMBIENT_WRITE_KEY']
    except KeyError as e:
        print('Missing environment variable: {}'.format(e))
        exit(1)

    am = ambient.Ambient(CHANNEL_ID, WRITE_KEY)

    # EnvSensorクラスの実体を作成します
    e = EnvSensor()
    # スレッドとして処理を開始します
    e.start()

    last_uploaded = datetime.now()
    while True:
        try:
            timestamp = datetime.now()
            if (timestamp - last_uploaded).seconds > 10:
                 am.send({
                    "d1": e.get_co2(),
                    "created": timestamp.strftime("%Y/%m/%d %H:%M:%S")
                })
            time.sleep(1)
        except KeyboardInterrupt:
            break
