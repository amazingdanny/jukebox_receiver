# receiver.py
import socket
import os

class RaspberryReceiver:
    def __init__(self, listen_ip: str, listen_port: int, folder_path: str,
                 audio_controller, ui_controller):
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.folder_path = folder_path
        self.audio_controller = audio_controller
        self.ui_controller = ui_controller

    def receive(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.listen_ip, self.listen_port))
            server.listen()
            while True:
                conn, addr = server.accept()
                with conn:
                    data = conn.recv(1024)
                    if not data:
                        continue
                    message = data.decode('utf-8').strip()
                    processed_message = self.handle_message(message)
                    # key commands
                    if message == 'K1':
                        self.audio_controller.skip()
                    elif message == 'K2':
                        self.audio_controller.pause()
                    elif message == 'K3':
                        self.audio_controller.resume()
                    else:
                        matching_files = self.find_matching_files(processed_message)
                        if matching_files:
                            print(f"Found matching files: {matching_files}")
                            file_to_play = matching_files[0]
                            full_path = os.path.join(self.folder_path, file_to_play)
                            self.audio_controller.play(full_path, file_to_play)
                            print(f"Playing file: {file_to_play}")

    def handle_message(self, message):
        if len(message) >= 2:
            return message[:3]
        return message

    def find_matching_files(self, pattern: str):
        matching_files = []
        if not os.path.exists(self.folder_path):
            return matching_files
        for filename in os.listdir(self.folder_path):
            file_path = os.path.join(self.folder_path, filename)
            if not os.path.isfile(file_path):
                continue
            try:
                if filename.startswith(pattern):
                    matching_files.append(filename)
            except Exception:
                continue
        return matching_files
