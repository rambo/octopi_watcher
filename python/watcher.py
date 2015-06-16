#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement
from __future__ import print_function
import logging
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.httpclient import AsyncHTTPClient

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

BUTTON_CHANNEL = 21
BOUNCE_TIME = 300

LOGLEVEL = logging.DEBUG
#LOGLEVEL = logging.INFO

class controller(object):
    pcbs = [] # List of active PeriodicCallback instances
    gpio_initialized = False

    def __init__(self, mainloop):
        self.mainloop = mainloop
        self.reload()

    def hook_signals(self):
        """Hooks POSIX signals to correct callbacks, call only from the main thread!"""
        import signal as posixsignal
        posixsignal.signal(posixsignal.SIGTERM, self.quit)
        posixsignal.signal(posixsignal.SIGQUIT, self.quit)
        posixsignal.signal(posixsignal.SIGHUP, self.reload)

    def reload(self, *args):
        """Reloads the configuration, will stop any and all periodic callbacks in flight"""
        # Stop the old ones
        for pcb in self.pcbs:
            pcb.stop()
        # And clean the list
        self.pcbs = []
        
        if self.gpio_initialized:
            GPIO.cleanup()

        GPIO.setup(BUTTON_CHANNEL, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(BUTTON_CHANNEL, GPIO.FALLING, callback=self.button_pressed, bouncetime=BOUNCE_TIME)
        self.gpio_initialized = True


    def quit(self, *args):
        self.mainloop.stop()
        if self.gpio_initialized:
            GPIO.cleanup()

    def run(self):
        self.mainloop.start()

    def button_pressed(self, *args):
        logging.debug("Button pressed")
        pass


if __name__ == '__main__':
    import sys
#    if len(sys.argv) < 2:
#        print("Usage: watcher.py config.yml")
#        sys.exit(1)
    # TODO: add a bsic formatter that gives timestamps etc
    logging.basicConfig(level=LOGLEVEL, stream=sys.stdout)
    loop = IOLoop.instance()
    instance = controller(loop)
    instance.hook_signals()
    try:
        instance.run()
    except KeyboardInterrupt:
        instance.quit()
