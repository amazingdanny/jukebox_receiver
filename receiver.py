import socket
import os
from audiocontroller import AudioController
from uicontroller import UIController  # Import UIController


class RaspberryReceiver:
    def __init__(self, listen_ip: str, listen_port: int, folder_path: str, audio_controller: AudioController,
                 ui_controller : UIController):
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.folder_path = folder_path
        self.audio_controller = audio_controller
        self.ui_controller = ui_controller  # Add UI controller reference

    def receive(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.listen_ip, self.listen_port))
            print(f"Listening on {self.listen_ip}:{self.listen_port}")
            server.listen()
            while True:
                conn, addr = server.accept()
                # Log connection to UI
                if self.ui_controller:
                    self.ui_controller.log_connection(f"{addr[0]}:{addr[1]}")

                with conn:
                    print(f"Connected by {addr}")
                    data = conn.recv(1024)
                    if not data:
                        continue
                    message = data.decode('utf-8').strip()

                    # Log message to UI
                    if self.ui_controller:
                        self.ui_controller.log_message(message)

                    print(f"Received raw message: '{message}'")
                    processed_message = self.handle_message(message)
                    print(f"Processed message: '{processed_message}'")
                    matching_files = self.find_matching_files(processed_message)
                    if matching_files:
                        file_to_play = matching_files[0]  # Get the first (and only) file
                        full_path = os.path.join(self.folder_path, file_to_play)
                        print(f"Found matching files: {matching_files}")

                        # Update UI with current song
                        #if self.ui_controller:
                            #self.ui_controller.update_song(file_to_play)

                        if processed_message == "K1":
                            print("pause")
                            if self.ui_controller:
                                self.ui_controller.set_playing_state(False)
                            # Add your pause logic here
                        else:
                            self.audio_controller.play(full_path, file_to_play)
                            #if self.ui_controller:
                                #self.ui_controller.set_playing_state(True)
                                #self.ui_controller.update_song(self.audio_controller.get_current_song())
                                #self.ui_controller.update_queue(self.audio_controller.get_current_queue())
                    else:
                        print(f"No files found for pattern: {processed_message}")

    def handle_message(self, message):
        # Extract first two characters if message is longer
        if len(message) >= 2:
            return message[:3]
        return message

    def find_matching_files(self, pattern: str):
        matching_files = []

        if not os.path.exists(self.folder_path):
            print(f"Folder path does not exist: {self.folder_path}")
            return matching_files

        for filename in os.listdir(self.folder_path):
            file_path = os.path.join(self.folder_path, filename)
            if not os.path.isfile(file_path):
                continue

            try:
                # Check if filename starts with the pattern
                if filename.startswith(pattern):
                    matching_files.append(filename)
            except Exception as e:
                print(f"Skipping {filename}: {e}")

        return matching_files