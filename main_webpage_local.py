import sounddevice as sd
import numpy as np
import threading
import time
import os
from datetime import datetime
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
import queue
import scipy.io.wavfile as wavfile  # Import scipy to write wav files
import csv
from flask import Flask, jsonify, render_template

# Initialize the Flask application
app = Flask(__name__)

# Initialize the BirdNET-Analyzer
analyzer = Analyzer()

# Audio parameters
BUFFER_DURATION = 10  # Duration of each audio chunk (seconds)
SAMPLE_RATE = 44100  # Sampling rate in Hz
CHANNELS = 1  # Mono channel

# A queue to hold audio chunks for processing
audio_queue = queue.Queue()

# Directory to save audio files
audio_dir = "bird_audio"
os.makedirs(audio_dir, exist_ok=True)  # Create the directory if it doesn't exist

# Global variable to store bird detections
detected_birds = []

# CSV log file (optional for storage, but we will not use it)
log_file = "bird_detections.csv"

# Initialize the CSV log file with headers (optional)
if not os.path.exists(log_file):
    with open(log_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Species', 'Confidence', 'Audio File'])

# Record audio in chunks and store in the queue
def record_audio(buffer_duration=BUFFER_DURATION, fs=SAMPLE_RATE, channels=CHANNELS):
    while True:
        print("Recording...")
        audio_chunk = sd.rec(int(buffer_duration * fs), samplerate=fs, channels=channels)
        sd.wait()  # Wait for the recording to complete
        audio_queue.put(audio_chunk)  # Add the recorded chunk to the queue
        print("Audio chunk stored in buffer")

# Analyze audio chunks using BirdNET Analyzer
def analyze_audio():
    global detected_birds
    while True:
        if not audio_queue.empty():
            audio_chunk = audio_queue.get()  # Get the latest audio chunk from the queue
            print("Analyzing audio chunk...")

            # Temporary audio file name for analysis
            temp_filename = "temp_audio.wav"
            
            # Use scipy to write the audio chunk to a file
            wavfile.write(temp_filename, SAMPLE_RATE, audio_chunk)

            # Analyze the audio using the BirdNET analyzer
            try:
                recording = Recording(
                    analyzer,
                    temp_filename,
                    lat=42.245,  # Latitude in decimal format
                    lon=3.04,    # Longitude in decimal format
                    date=datetime.now(),  # Current timestamp
                    min_conf=0.5  # Minimum confidence threshold for detections
                )
                recording.analyze()

                # Check if any species are detected
                if recording.detections:
                    for detection in recording.detections:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        species = detection['common_name']
                        confidence = detection['confidence']
                        print(f"Detected bird: {species} with confidence {confidence}")

                        # Save the audio file
                        audio_filename = os.path.join(audio_dir, f"bird_{timestamp.replace(' ', '_').replace(':', '-')}.wav")
                        wavfile.write(audio_filename, SAMPLE_RATE, audio_chunk)

                        # Log the detection in the global list
                        detected_birds.append({
                            'timestamp': timestamp,
                            'species': species,
                            'confidence': confidence,
                            'audio_file': audio_filename
                        })

                        # Also log to CSV (optional)
                        with open(log_file, mode='a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow([timestamp, species, confidence, audio_filename])

                else:
                    print("No birds detected. Audio file not saved.")

            except Exception as e:
                print(f"Error during bird detection: {e}")

        time.sleep(1)  # Allow time for the next chunk to be recorded

# Flask route for the main page
@app.route('/')
def index():
    return render_template('index.html')

# Flask API endpoint to get the list of detected birds
@app.route('/detected_birds', methods=['GET'])
def get_detected_birds():
    return jsonify(detected_birds)

if __name__ == '__main__':
    # Start the recording thread
    record_thread = threading.Thread(target=record_audio)
    record_thread.daemon = True
    record_thread.start()

    # Start the analyzing thread
    analyze_thread = threading.Thread(target=analyze_audio)
    analyze_thread.daemon = True
    analyze_thread.start()

    # Start the Flask web server
    app.run(host="0.0.0.0", port=5000)
