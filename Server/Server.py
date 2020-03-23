import socket
import math
import time
from threading import Thread, Lock

'''
Coords for test:

Driver
    Lat: -19.9072415
    Lon: -43.9018246
    
Passenger
    init
        Lat: -19.9064481
        Lon: -43.9010775
    Begin
        -19.9064481,-43.9010775
    End
        -19.93377,-43.9272734
'''

clients = {}
clients_lock = Lock()


class ClientThread(Thread):
    user = {}

    def __init__(self, client_address, client_socket):
        Thread.__init__(self)
        self.csocket = client_socket
        self.user['address'] = client_address[1]
        print("New connection added: ", client_address)

    def run(self):
        # Register new user
        user_data = self.csocket.recv(2048)
        user_type, user_name, car_brand, car_model, car_plate, lat, lon = user_data.decode().split('|')

        '''
        Status codes:
            0 - waiting
            1 - connected
            2 - searching
            3 - control
        '''
        new_user = {
            'name': user_name,
            'type': user_type.lower(),
            'status': 3,
            'address': self.user['address']
        }

        if user_type.lower().startswith('d'):
            new_user['carBrand'] = car_brand
            new_user['carModel'] = car_model
            new_user['carPlate'] = car_plate

        new_user['lat'] = float(lat)
        new_user['lon'] = float(lon)
        self.user = new_user
        with clients_lock:
            clients[str(self.user['address'])] = self

        self.csocket.send(bytes('Welcome {}!| '.format(user_name), 'UTF-8'))
        print('New user registered.\nName: {}\nType: {}\nAddress: {}'.format(user_name, user_type, self.user['address']))

        time.sleep(0.3)

        # User listener
        if user_type.lower().startswith('p'):
            drivers = self.find_all_in_prox(max_distance=10)
            while True:
                if self.user['status'] == 3:
                    self.user['status'] = 0
                    drivers = self.find_all_in_prox(max_distance=10)
                    self.csocket.send(bytes('\n{} drivers near you.| '.format(
                        len(drivers)
                    ), 'UTF-8'))
                    continue

                data = self.csocket.recv(2048).decode().split('|')
                if data[0] == 'exit':
                    break

                if self.user['status'] == 0:
                    if data[0] == 'find':
                        self.csocket.send(bytes('\nBegin: (lat,lon)| ', 'UTF-8'))
                        init = self.csocket.recv(2048).decode().split('|')[0].split(',')
                        self.csocket.send(bytes('\nEnd: (lat, lon)| ', 'UTF-8'))
                        end = self.csocket.recv(2048).decode().split('|')[0].split(',')
                        distance = self.calculate_distance(
                            coords1=(float(init[0]), float(init[1])),
                            coords2=(float(end[0]), float(end[1]))
                        )
                        price = 6.12+(distance*1.12)

                        print(distance, price)

                        self.csocket.send(bytes('\nDistance: {:.1f} km\nPrice: R$ {:.2f}\nOK to continue...| '.format(
                            distance,
                            price
                        ), 'UTF-8'))
                        is_ok = self.csocket.recv(2048).decode().split('|')[0]
                        if 'ok' in is_ok.lower():
                            self.user['status'] = 2
                            self.csocket.send(bytes('\nSearching drivers in proximity...| ', 'UTF-8'))
                            drivers = self.find_all_in_prox(max_distance=10, lat=float(init[0]), lon=float(init[1]))
                            for d in drivers:
                                clients[d].user['status'] = 2
                                clients[d].csocket.send(bytes('\nUser {:.1f} km far from you. (Accept/Reject)|{}'.format(
                                    self.calculate_distance(
                                        coords1=(float(init[0]), float(init[1])),
                                        coords2=(clients[d].user['lat'], clients[d].user['lon'])
                                    ), client_address[1]
                                ), 'UTF-8'))
                        else:
                            self.user['status'] = 3

                elif self.user['status'] == 2:
                    if data[0] == 'stop':
                        self.user['status'] = 3

                else:
                    if data[0] == 'found' and len(data) > 1 and self.user['status'] == 1:
                        self.listener(client_dest_address=data[1])

        else:
            while True:
                if self.user['status'] == 3:
                    self.user['status'] = 0
                    time.sleep(0.2)
                    self.csocket.send(bytes('\nYou are now available.| ', 'UTF-8'))
                    continue

                data = self.csocket.recv(2048).decode().split('|')
                if data[0] == 'exit':
                    break

                if self.user['status'] == 0:
                    pass

                elif self.user['status'] == 2:
                    if data[0].lower().startswith('a'):
                        self.listener(client_dest_address=data[1])
                    else:
                        self.csocket.send(bytes('\nRun rejected. You cannot accept any run for 10 secs.| ', 'UTF-8'))
                        time.sleep(10)
                        self.user['status'] = 3

        print("Client at ", self.user['address'], " disconnected...")
        with clients_lock:
            del clients[str(self.user['address'])]
            self.csocket.close()

    def find_all_in_prox(self, max_distance=10, lat=None, lon=None):
        lat = lat if lat else self.user['lat']
        lon = lon if lon else self.user['lon']
        return [
            d for d in list(clients) if clients[d].user['type'].lower().startswith('d') and
            self.calculate_distance(
                coords1=(lat, lon),
                coords2=(clients[d].user['lat'], clients[d].user['lon'])
            ) <= max_distance and
            clients[d].user['status'] == 0
        ]

    @staticmethod
    def calculate_distance(coords1, coords2):
        radius = 6373.0
        lat1, lon1 = math.radians(coords1[0]), math.radians(coords1[1])
        lat2, lon2 = math.radians(coords2[0]), math.radians(coords2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = \
            math.sin(dlat/2)**2 + \
            math.cos(lat1) * math.cos(lat2) * \
            math.sin(dlon/2)**2

        center = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = radius * center

        return distance

    def listener(self, client_dest_address):
        to_send = clients.get(client_dest_address)
        if not to_send:
            self.user['status'] = 3
            return
        to_send.user['status'] = 1
        self.user['status'] = 1
        if self.user['type'] == 'driver':
            to_send.csocket.send(bytes('found|{}'.format(self.user['address']), 'UTF-8'))
            self.csocket.send(bytes('\nConnected with {}| '.format(to_send.user['name']), 'UTF-8'))
        else:
            self.csocket.send(bytes('\nConnected with {} - {} {} plate {}| '.format(
                to_send.user['name'],
                to_send.user['carBrand'],
                to_send.user['carModel'],
                to_send.user['carPlate']
            ), 'UTF-8'))

        try:
            while True:
                data = self.csocket.recv(2048)
                if not data.decode().split('|')[0]:
                    self.user['status'] = 3
                    time.sleep(0.2)
                    self.csocket.send(bytes('\nDisconnected.| ', 'UTF-8'))
                    if to_send.user['status'] == 1:
                        to_send.user['status'] = 3
                        to_send.csocket.send(bytes('disconnected_from_user| ', 'UTF-8'))
                    return
                with clients_lock:
                    to_send.csocket.send(data)
        except Exception as e:
            with clients_lock:
                del clients[str(client_address[1])]
                self.csocket.close()


LOCALHOST = "127.0.0.1"
PORT = 8080
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((LOCALHOST, PORT))
print("Server started")
print("Waiting for client request..")

while True:
    server.listen(1)
    # conexão feita aqui
    client_sock, client_address = server.accept()
    # criação da thread
    new_thread = ClientThread(client_address, client_sock)
    # inicio da execução da thread
    new_thread.start()
