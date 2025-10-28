from audiocontroller import AudioController
from receiver import RaspberryReceiver


def main():
    print("starting")
    audio_controller = AudioController()
    print("controller created")
    receiver = RaspberryReceiver("0.0.0.0", 5000,'/mnt/usb', audio_controller)
    print("receiver created")
    receiver.receive()
    print("exiting")

if __name__ == "__main__":
    main()