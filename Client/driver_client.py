import socket
import time
import threading


def printer(lock):
    global connected_to
    global connected
    while True:
        time.sleep(0.3)
        try:
            with lock:
                in_data = client.recv(1024).decode().split('|')
                if not in_data[0]:
                    continue
                if in_data[0] == 'disconnected_from_user':
                    client.send(bytes('|{}'.format(connected_to), 'UTF-8'))
                    continue
                if in_data and in_data[1].isdigit():
                    connected_to = in_data[1]
                    connected = True
                print(in_data[0])
        except Exception as e:
            print(e)


SERVER = "127.0.0.1"
PORT = 8080
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

userName = input('Your name: ')
userType = 'driver'
carBrand = input('Car brand: ') or ''
carModel = input('Car model: ') or ''
carPlate = input('Car plate: ') or ''
lat = input('Latitude: ')
lon = input('Longitude: ')

client.connect((SERVER, PORT))
client.sendall(bytes('{}|{}|{}|{}|{}|{}|{}'.format(
    userType, userName,
    carBrand, carModel, carPlate,
    lat, lon
), 'UTF-8'))

connected_to = ''
connected = False

lock = threading.Lock()
p = threading.Thread(target=printer, args=(lock,), daemon=True)
p.start()

while True:
    out_data = input()
    client.sendall(bytes('{}|{}'.format(out_data, connected_to), 'UTF-8'))
    if out_data == 'exit':
        break
client.close()
