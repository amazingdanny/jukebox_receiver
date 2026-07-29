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
        self.is_paused = False

    def receive(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.listen_ip, self.listen_port))
            server.listen()
            while True:
                conn, addr = server.accept()
                print(f"Connected by {addr}")
                with conn:
                    data = conn.recv(1024)
                    print(f"Received data: {data}")
                    if not data:
                        continue
                    message = data.decode('utf-8').strip()
                    processed_message = self.handle_message(message)
                    print(f"message : {message}")
                    # key commands
                    if message == 'K01':
                        self.audio_controller.skip()
                    elif message == 'K02':
                        self.audio_controller.handle_pause()
                    elif message == 'K03':
                        self.audio_controller.resume()
                    elif message == 'K04':
                        self.audio_controller.clear_queue()
                    elif message == 'K05':
                        self.audio_controller.play_random_song(self.folder_path)
                    elif message == 'K06':
                        self.audio_controller.queue_random_songs(self.folder_path)
                    else:
                        matching_files = self.find_matching_files(processed_message)
                        print(f"found matching files {matching_files}")
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
