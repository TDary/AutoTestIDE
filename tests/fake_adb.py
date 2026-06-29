"""Fake adb binary for testing AdbForwarder and DeviceManager.

Invoked as: python tests/fake_adb.py [adb args...]
Mimics: adb devices -l, adb -s <serial> forward tcp:0 tcp:<port>,
        adb -s <serial> forward --remove tcp:<port>
"""
import sys


def main(argv):
    # adb devices -l
    if len(argv) >= 2 and argv[0] == "devices" and argv[1] == "-l":
        sys.stdout.write(
            "List of devices attached\n"
            "emulator-5554   device product:sdk_phone model:Pixel_6 device:emu transport_id:1\n"
            "deadbeef        offline transport_id:2\n"
            "cafebabe        unauthorized transport_id:3\n"
        )
        return 0

    # adb -s <serial> forward tcp:0 tcp:<remote_port>
    if len(argv) >= 3 and argv[0] == "-s" and argv[2] == "forward":
        sys.stdout.write("12345\n")
        return 0

    # adb -s <serial> forward --remove tcp:<port>
    if len(argv) >= 4 and argv[0] == "-s" and argv[2] == "forward" and argv[3] == "--remove":
        return 0

    # Unknown command
    sys.stderr.write(f"fake_adb: unknown command: {argv}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
