#!/usr/bin/env python

import alsaaudio
import logging
import os
import pygame
import signal
import sys
import threading
import time

import RPi.GPIO as GPIO


# -----------------------------------------------------------------------------
# LED definitions

class LED(object):
    class _Blinker(threading.Thread):
        def __init__(self, channel):
            threading.Thread.__init__(self)
            self.channel = channel
            self._stop = False

        def run(self):
            state = False
            while not self._stop:
                state = not state
                GPIO.output(self.channel, state)
                time.sleep(0.5)

        def stop(self):
            self._stop = True

    def __init__(self, channel):
        logging.info("led: __init__(%d)", channel)
        self.channel = channel
        self._blinker = None
        GPIO.setup(self.channel, GPIO.OUT)
        GPIO.output(self.channel, False)

    def blink(self, start=True):
        logging.info("led: blink(%s)", start)
        if start and self._blinker is None:
            self._blinker = self._Blinker(self.channel)
            self._blinker.start()
        elif not start and self._blinker is not None:
            self._blinker.stop()
            self._blinker.join()
            self._blinker = None

    def on(self):
        logging.info("led: on()")
        self.blink(False)
        GPIO.output(self.channel, True)

    def off(self):
        logging.info("led: off()")
        self.blink(False)
        GPIO.output(self.channel, False)


# -----------------------------------------------------------------------------
# AUDIO definitions

AUDIO_STOPPED = 0
AUDIO_STARTED = 1
AUDIO_PAUSED = 2

AUDIO_STATE_STRING = {
    AUDIO_STOPPED: "stopped",
    AUDIO_STARTED: "started",
    AUDIO_PAUSED: "paused",
}


class AUDIO(object):
    def __init__(self, audio_file, start_channel, stop_channel, led):
        logging.info("audio: __init__(%s, %d, %d, %d)", audio_file,
                     start_channel, stop_channel, led.channel)
        self.audio_file = audio_file
        self.start_channel = start_channel
        self.stop_channel = stop_channel
        self.led = led
        self.state = AUDIO_STOPPED

        GPIO.setup(start_channel, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(start_channel, GPIO.FALLING, callback=self._cb,
                              bouncetime=500)
        GPIO.setup(stop_channel, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(stop_channel, GPIO.FALLING, callback=self._cb,
                              bouncetime=500)

    def _cb(self, channel):
        if channel == self.start_channel:
            if self.state == AUDIO_STARTED:
                self.pause()
            elif self.state == AUDIO_PAUSED:
                self.unpause()
            else:
                self.start()
        else:
            if self.state != AUDIO_STOPPED:
                self.stop()

    def _set_state(self, state):
        logging.info("audio: _set_state: %s -> %s",
                     AUDIO_STATE_STRING[self.state], AUDIO_STATE_STRING[state])
        self.state = state

    def start(self):
        logging.info("audio: start")
        self._set_state(AUDIO_STARTED)
        pygame.mixer.music.load(self.audio_file)
        pygame.mixer.music.play()
        self.led.on()

    def pause(self):
        logging.info("audio: pause")
        self._set_state(AUDIO_PAUSED)
        pygame.mixer.music.pause()
        self.led.blink()

    def unpause(self):
        logging.info("audio: unpause")
        self._set_state(AUDIO_STARTED)
        pygame.mixer.music.unpause()
        self.led.on()

    def stop(self):
        logging.info("audio: stop")
        self._set_state(AUDIO_STOPPED)
        pygame.mixer.music.stop()
        self.led.off()


# -----------------------------------------------------------------------------
# MIXER definitions

class MIXER(object):
    def __init__(self):
        logging.info("mixer: __init__()")

        # Setup the ALSA mixer
        mixer = alsaaudio.Mixer(control="PCM", cardindex=0)
        mixer.setvolume(100)

        # Setup SDL for pygame
        os.putenv('AUDIODEV', 'plug:default:0')
        os.putenv('SDL_AUDIODRIVER', 'alsa')

        # Setup the pygame mixer
        pygame.mixer.init(44100, -16, 2, 4096)
        pygame.mixer.music.set_volume(1.0)


# -----------------------------------------------------------------------------
# Misc functions definitions

def cleanup(signum, frame):
    logging.info("received signal: %d", signum)
    GPIO.cleanup()
    pygame.mixer.quit()
    sys.exit(0)


# -----------------------------------------------------------------------------
# Main entry point

def main():
    led_green_channel = 22
    led_yellow_channel = 24

    audio_start_channel = 16
    audio_stop_channel = 18

    audio_file = '/home/pi/maria.mp3'

    mixer = MIXER()

    GPIO.setmode(GPIO.BOARD)

    led_green = LED(led_green_channel)
    led_green.on()

    led_yellow = LED(led_yellow_channel)
    led_yellow.off()

    audio = AUDIO(audio_file, audio_start_channel, audio_stop_channel,
                  led_yellow)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    first = True
    while True:
        if ((audio.state != AUDIO_STOPPED and
             not pygame.mixer.music.get_busy())):
            logging.info("maria: audio stopped")
            audio.stop()
        if first:
            logging.info("maria: started")
            first = False
        time.sleep(1)


if __name__ == "__main__":
    log_file = "/scratch/maria.log"
    log_fmt = '%(asctime)-6s: %(name)s - %(levelname)s - %(message)s'
    log_level = logging.INFO

    logging.basicConfig(filename=log_file, level=log_level, format=log_fmt)
    # logging.basicConfig(level=log_level, format=log_fmt)

    try:
        main()
    except:
        logging.exception('')
        raise
