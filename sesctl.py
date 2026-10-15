"""Local lifecycle diagnostics; no microphone capture or model loading."""
import argparse
import json
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket

def request(command):
    socket=QLocalSocket()
    socket.connectToServer('arda-ses-local-v1')
    if not socket.waitForConnected(1200):
        raise RuntimeError('Tını çalışmıyor')
    socket.write(command.encode())
    socket.waitForBytesWritten(1000)
    if not socket.waitForReadyRead(2000):
        raise RuntimeError('Tını yanıt vermiyor')
    response=json.loads(bytes(socket.readAll()))
    socket.close()
    return response

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['status','show','quit'])
    args=parser.parse_args()
    app=QCoreApplication([])
    print(json.dumps(request(args.command)))
