#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement
from __future__ import print_function
import logging
import yaml
import json
import time
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado import gen
from tornado.httpclient import AsyncHTTPClient

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

LOGLEVEL = logging.DEBUG
#LOGLEVEL = logging.INFO

class controller(object):
    config = {}
    pcbs = [] # List of active PeriodicCallback instances
    gpio_initialized = False
    job_last_active = None

    def __init__(self, config_file, mainloop):
        self.config_file = config_file
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

        with open(self.config_file) as f:
            self.config = yaml.load(f)

        self.register_power_callback()

        if self.gpio_initialized:
            GPIO.cleanup()

        GPIO.setup(self.config['BUTTON_CHANNEL'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.config['BUTTON_CHANNEL'], GPIO.FALLING, callback=self.button_pressed, bouncetime=self.config['BOUNCE_TIME'])
        self.gpio_initialized = True


    def register_power_callback(self):
        self.mainloop.spawn_callback(self.check_power)
        pcb = PeriodicCallback(self.check_power, int(self.config['MAIN_POWER_CHECK_INTERVAL']*1000))
        pcb.start()
        self.pcbs.append(pcb)

    def quit(self, *args):
        self.mainloop.stop()
        if self.gpio_initialized:
            GPIO.cleanup()

    def run(self):
        self.mainloop.start()

    @gen.coroutine
    def check_power(self):
        logging.debug("check_power called, current time %s" % (self.mainloop.time()))
        try:
            extra_headers = { 'X-Api-Key': self.config['API_KEY'] }
            url = "%s/api/job" % self.config['API_BASE_URL']
            response = yield AsyncHTTPClient().fetch(url, request_timeout=1, headers=extra_headers)
            if response.error:
                logging.warning("Got exception %s when fetching %s" % (response.error, url))
            else:
                logging.info("Fetched %s in %s seconds" % (url, response.request_time))
                decoded = json.loads(response.body)
                logging.debug("Decoded response %s" % repr(decoded))
                if decoded['state'] == 'Printing':
                    self.job_last_active = time.time()
        except Exception, e:
            logging.exception(e)
        
        if self.job_last_active:
            if time.time() - self.job_last_active > self.config['MAIN_POWER_TIMEOUT']:
                self.mainloop.spawn_callback(self.disable_printer_power)
                
            

    @gen.coroutine
    def enable_printer_power(self):
        try:
            logging.info("Enabling printer power")
            self.job_last_active = time.time()
        except Exception, e:
            logging.exception(e)
        pass

    @gen.coroutine
    def disable_printer_power(self):
        try:
            logging.info("Disabling printer power after %s seconds of inactivity" % self.config['MAIN_POWER_TIMEOUT'])
        except Exception, e:
            logging.exception(e)
        pass

    def button_pressed(self, *args):
        logging.debug("Button pressed")
        self.mainloop.spawn_callback(self.enable_printer_power)
        pass


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: watcher.py config.yml")
        sys.exit(1)
    # TODO: add a bsic formatter that gives timestamps etc
    logging.basicConfig(level=LOGLEVEL, stream=sys.stdout)
    loop = IOLoop.instance()
    instance = controller(sys.argv[1], loop)
    instance.hook_signals()
    try:
        instance.run()
    except KeyboardInterrupt:
        instance.quit()
