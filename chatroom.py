import socket
import threading
import sys
import time

allmessages = []
lock = threading.Lock()
clients = {}


def save_messages():
    with lock:
        with open('messages.txt', 'w', encoding="utf-8") as file:
            for msg in allmessages:
                file.write(msg + '\n')
        print('Messages saved!')


def get_client_info(requesting_socket):
    with lock:
        other_clients = [
            f"name: {info['name']},lastname:{info['lastname']},username:{info['username']},ip:{info['ip']} "
            for sock, info in clients.items() if sock != requesting_socket
        ]
        return "\n".join(other_clients) if other_clients else "No other clients connected."


def echo(newSocket, address):
    username = "unknown"
    try:
        initial_msg = newSocket.recv(1024).decode()
        if not initial_msg or '|' not in initial_msg:
            return
        name, lastname, username, ip = initial_msg.split('|')
        if not ip:
            ip = address[0]

        with lock:
            clients[newSocket] = {
                "name": name,
                "lastname": lastname,
                "username": username,
                "ip": ip,
                "address": address
            }
        print(f"Client {username} connected")

        while True:
            msg = newSocket.recv(1024)
            if not msg:
                break
            decoded_msg = msg.decode()

            if 'disconnected' in decoded_msg.lower() or 'exit' in decoded_msg.lower():
                print(f"Client {username} left the chat: {decoded_msg}")
                break

            if decoded_msg.lower().endswith(':getinfo'):
                info = get_client_info(newSocket)
                newSocket.sendall(f"Client info:\n{info}".encode())
                continue

            if decoded_msg.lower().endswith(':test_disconnect'):
                newSocket.close()
                break

            if decoded_msg.lower().startswith('editinfo|'):
                try:
                    _, name, lastname, username_new, ip = decoded_msg.split('|')
                    if not ip:
                        ip = address[0]
                    with lock:
                        clients[newSocket] = {
                            "name": name,
                            "lastname": lastname,
                            "username": username_new,
                            "ip": ip,
                            "address": address
                        }
                    username = username_new
                    newSocket.sendall(f"Info updated for {username}".encode())
                    print(f"Client {username} updated their info")
                except ValueError:
                    newSocket.sendall("Error: Invalid editinfo format".encode())
                continue

            with lock:
                allmessages.append(decoded_msg)

            print(f"Received: {decoded_msg}")

            if 'save' in decoded_msg.lower():
                save_messages()
            else:
                newSocket.sendall(msg)
    except (ConnectionError, UnicodeDecodeError, ValueError) as e:
        print(f"Error in connection: {e}")
    finally:
        with lock:
            if newSocket in clients:
                username = clients[newSocket]["username"]
                del clients[newSocket]
        newSocket.close()



def server():
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mySocket.bind(('0.0.0.0', 9090))
    mySocket.listen()
    print("Server started on port 9090")

    try:
        while True:
            newSocket, addr = mySocket.accept()
            print("new user joined")
            threading.Thread(target=echo, args=(newSocket, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("Server shutting down")
    finally:
        mySocket.close()
        print("Server socket closed")


def client():
    user_info = {}
    mySocket = None

    def connect_to_server():
        nonlocal mySocket
        try:
            mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mySocket.connect(('127.0.0.1', 9090))
            print("Connected to server")
            return True
        except ConnectionRefusedError:
            print("Could not connect to server. Is it running?")
            return False

    def send_initial_info():
        initial_info = f"{user_info['name']}|{user_info['lastname']}|{user_info['username']}|{user_info['ip']}"
        mySocket.sendall(initial_info.encode())

    try:
        if not user_info:
            name = input("enter your name: ").strip()
            if not name:
                print("name cannot be empty")
                return
            lastname = input("enter your last name: ").strip()
            if not lastname:
                print("lastname cannot be empty")
                return
            username = input('Enter your username: ').strip()
            if not username:
                print("Username cannot be empty!")
                return
            ip = input('Enter your IP (leave empty to use default): ').strip()
            user_info.update({
                "name": name,
                "lastname": lastname,
                "username": username,
                "ip": ip
            })

        if not connect_to_server():
            print("Attempting to reconnect every 2 minutes...")
            while not connect_to_server():
                try:
                    time.sleep(120)
                except KeyboardInterrupt:
                    print("\nReconnect interrupted. Exiting...")
                    return
            print("Reconnected successfully")
        send_initial_info()

        while True:
            try:
                msg = input("Enter a message (or 'editinfo' to update info): ").strip()
                if not msg:
                    print("Message cannot be empty!")
                    continue

                if msg.lower() == 'exit':
                    mySocket.sendall(f"{user_info['username']}:exit".encode())
                    break

                if msg.lower() == 'test_disconnect':
                    mySocket.sendall(f"{user_info['username']}:disconnected".encode())
                    mySocket.close()
                    print("Simulating connection loss...")
                    print("Attempting to reconnect every 2 minutes...")
                    time.sleep(120)
                    while not connect_to_server():
                        try:
                            time.sleep(120)
                        except KeyboardInterrupt:
                            print("\nReconnect interrupted. Exiting...")
                            return
                    print("Reconnected successfully")
                    send_initial_info()
                    continue

                if msg.lower() == 'editinfo':
                    name = input('Enter new name: ').strip()
                    if not name:
                        print("Name cannot be empty!")
                        continue
                    lastname = input('Enter new lastname: ').strip()
                    if not lastname:
                        print("Lastname cannot be empty!")
                        continue
                    username_new = input('Enter new username: ').strip()
                    if not username_new:
                        print("Username cannot be empty!")
                        continue
                    ip = input('Enter new IP (leave empty to use default): ').strip()

                    user_info.update({
                        "name": name,
                        "lastname": lastname,
                        "username": username_new,
                        "ip": ip
                    })
                    edit_info = f"editinfo|{name}|{lastname}|{username_new}|{ip}"
                    mySocket.sendall(edit_info.encode())
                    result = mySocket.recv(2048).decode()
                    print(f"Server response: {result}")
                    continue

                mySocket.sendall(f"{user_info['username']}:{msg}".encode())
                result = mySocket.recv(2048).decode()
                print(f"Server response: {result}")
            except (ConnectionError, ConnectionResetError, BrokenPipeError) as e:
                print(f"Connection error: {e}")
                print("Connection lost. Attempting to reconnect every 2 minutes...")
                mySocket.close()
                while not connect_to_server():
                    try:
                        time.sleep(120)
                    except KeyboardInterrupt:
                        print("\nReconnect interrupted. Exiting...")
                        return
                print("Reconnected successfully")
                send_initial_info()
                continue
            except KeyboardInterrupt:
                print("\nClient interrupted. Sending disconnect message...")
                mySocket.sendall(f"{user_info['username']}:exit".encode())
                break

    finally:
        if mySocket:
            mySocket.close()
            print("Client socket closed")

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ['server', 'client']:
        print("Usage: python chat.py [server|client]")
        return

    mode = sys.argv[1]
    if mode == 'server':
        server()
    elif mode == 'client':
        client()


if __name__ == "__main__":
    main()
