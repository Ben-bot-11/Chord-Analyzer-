# Chord Analyzer

Chord Analyzer is a lightweight Python tool designed to identify musical chords from audio input. It converts raw sound into pitch information, maps those pitches to musical notes, and determines the most likely chord being played. The tool also includes a basic tuner function that measures pitch deviations in cents.

---

## Features

- Supports both microphone input and pre-recorded audio files.
- Detects fundamental frequencies and converts them into musical note names.
- Determines chord quality (e.g., major, minor) based on detected pitch sets.
- Includes a tuner mode for evaluating intonation accuracy.
- Lightweight, fast, and easy to extend.

---

**How It Works**

Audio Processing
The program processes incoming audio to extract fundamental frequencies using standard signal processing libraries.

Pitch Mapping
Each detected frequency is mapped to the nearest equal-tempered note.

Chord Recognition
Notes are analyzed as a pitch-class set to determine the most probable chord quality and root.

Tuner Function
For single notes, the deviation from standard tuning (A4 = 440 Hz) is measured and displayed. (The A4 frequency is adjustable)

**Planned improvements (see TODO file for details):**
Support for extended chords (major 7th, minor 7th, dominant 7th, 9th, etc.)

Graphical user interface

Improved frequency smoothing and pitch tracking

Chord inversion identification

Visualization of detected frequency amplitudes

