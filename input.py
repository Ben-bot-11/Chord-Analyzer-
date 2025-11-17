import math
import queue
import threading
from collections import deque, Counter

import numpy as np
import sounddevice as sd

import aubio



MODULE_NAME = "chords"  
mod = __import__(MODULE_NAME)
analyze = getattr(mod, "analyze")


# ---------------------------------------------------------------------------
# Audio / detection settings
# ---------------------------------------------------------------------------
SAMPLE_RATE   = 44100
BLOCK_SIZE    = 2048         
HOP_SIZE      = BLOCK_SIZE
METHOD        = "yin"
CONF_THRESH   = 0.81
SMOOTH_N      = 5
STABLE_FRAMES = 20

DEVICE_INDEX  = None
CHANNELS      = 1
prefer_flats_default = False


PC_TO_SHARP = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
A4 = 440.0

def freq_to_midi(f):
    if f <= 0:
        return None
    return int(round(12 * math.log2(f / A4) + 69))

def midi_to_pc(midi):
    return None if midi is None else (midi % 12)

def pc_to_name(pc):
    return PC_TO_SHARP[pc]

def most_frequent(items):
    if not items:
        return None
    c = Counter(items)
    return c.most_common(1)[0][0]


audio_q = queue.Queue()

class Controller:
    def __init__(self):
        self.running = False
        self.quit = False
        self.lock = threading.Lock()
        self.session_pcs = []

    def set_running(self, val):
        with self.lock:
            self.running = val

    def append_pc(self, pc_name_no_octave):
        with self.lock:
            if self.running:
                self.session_pcs.append(pc_name_no_octave)

    def take_session_pcs_and_reset(self):
        with self.lock:
            pcs = self.session_pcs
            self.session_pcs = []
            return pcs

controller = Controller()

def cmd_thread():
    print("\nCommands:\n"
          "  start\n"
          "  end\n"
          "  device\n"
          "  quit\n")
    while not controller.quit:
        try:
            raw = input("Put commands here: ")
        except EOFError:
            raw = "quit"

        cmd = (raw or "").strip().lower()
        if not cmd:
            continue

        tokens = cmd.split()
        head = tokens[0]
        rest = tokens[1:]

        if head == "start":
            if controller.running:
                print("Already running.")
            else:
                controller.set_running(True)
                print("Detecting.")

        elif head == "end":
            if not controller.running:
                print("Not running.")
                continue
            controller.set_running(False)
            pcs = controller.take_session_pcs_and_reset()
            unique_ordered, seen = [], set()
            for p in pcs:
                if p not in seen:
                    seen.add(p)
                    unique_ordered.append(p)
            if len(unique_ordered) < 2:
                if len(unique_ordered) == 1:
                    print("single Note " + unique_ordered[0])
                else:
                    print("Ended. No notes were detected.")
            else:
                print("Detected: ", unique_ordered)
                try:
                    analyze(unique_ordered, prefer_flats=prefer_flats_default)
                except Exception as e:
                    print("analyze() error:", e)
            print("Waiting to start…")

        elif head in ("device", "devices") or (head == "device" and rest and rest[0] == "check"):
            print("\ndevices")
            print(sd.query_devices())
            try:
                info = sd.query_devices(kind='input')
                name = info.get('name', None)
                print("\nCurrent default input:", name if name else info)
            except Exception as e:
                print("\nNo input device detected:", e)
            print("Set index from the script for a specific input.\n")

        elif head == "quit":
            controller.quit = True
            print("HelloWorld")

        elif head in ("help", "?"):
            print("\nCommands:\n"
                  "  start\n"
                  "  end\n"
                  "  device\n"
                  "  quit\n")
        else:
            print("Unknown command.")

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_q.put(indata[:, 0].copy())

def main():
    pitch_o = aubio.pitch(METHOD, BLOCK_SIZE, HOP_SIZE, SAMPLE_RATE)
    pitch_o.set_unit("Hz")
    pitch_o.set_silence(-40)

    smooth_names = deque(maxlen=SMOOTH_N)
    last_emitted = None
    stable_counter = 0

    t = threading.Thread(target=cmd_thread, daemon=True)
    t.start()

    stream_kwargs = dict(
        channels=CHANNELS,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="float32",
        callback=audio_callback
    )
    if DEVICE_INDEX is not None:
        stream_kwargs["device"] = DEVICE_INDEX

    print("'start' to begin, 'end' to analyze, 'quit' to exit.")
    with sd.InputStream(**stream_kwargs):
        while not controller.quit:
            try:
                block = audio_q.get(timeout=0.5)
            except queue.Empty:
                continue

            if block.dtype != np.float32:
                block = block.astype(np.float32)

            f0 = float(pitch_o(block).item())
            conf = float(pitch_o.get_confidence())

            if not controller.running:
                smooth_names.clear()
                last_emitted = None
                stable_counter = 0
                continue

            if f0 > 0 and conf >= CONF_THRESH:
                midi = freq_to_midi(f0)
                if midi is None:
                    continue
                pc = midi_to_pc(midi)
                name_with_oct = pc_to_name(pc) + str(midi // 12 - 1)
                smooth_names.append(name_with_oct)

                smoothed = most_frequent(list(smooth_names))
                if smoothed is None:
                    continue

                if smoothed == last_emitted:
                    stable_counter = min(stable_counter + 1, 1000000)
                else:
                    recent = list(smooth_names)[-min(STABLE_FRAMES, len(smooth_names)):]
                    if recent and all(x == smoothed for x in recent):
                        last_emitted = smoothed
                        stable_counter = 0
                        print(f"\rNote: {smoothed:<6s}  f0≈{f0:7.2f} Hz  conf={conf:0.2f}      ", end="")
                        controller.append_pc(smoothed[:-1])

            else:
                pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("HelloWorld.")
