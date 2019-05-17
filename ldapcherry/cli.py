#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:set expandtab tabstop=4 shiftwidth=4:
# The MIT License (MIT)
# LdapCherry
# Copyright (c) 2014 Carpentier Pierre-Francois

"""The CherryPy daemon."""

import sys
import os.path

import cherrypy
from cherrypy.process import plugins, servers
from cherrypy import Application
from ldapcherry import LdapCherry
import configparser

def start(configfile=None, daemonize=False, environment=None,
          fastcgi=False, scgi=False, pidfile=None,
          cgi=False, debug=False,context_root='/'):
    """Subscribe all engine plugins and start the engine."""
    sys.path = [''] + sys.path

    # monkey patching cherrypy to disable config interpolation
    def new_as_dict(self, raw=True, vars=None):
        """Convert an INI file to a dictionary"""
        # Load INI file into a dict
        result = {}
        for section in self.sections():
            if section not in result:
                result[section] = {}
            for option in self.options(section):
                value = self.get(section, option, raw=raw, vars=vars)
                try:
                    value = cherrypy.lib.reprconf.unrepr(value)
                except Exception:
                    x = sys.exc_info()[1]
                    msg = ("Config error in section: %r, option: %r, "
                           "value: %r. Config values must be valid Python." %
                           (section, option, value))
                    raise ValueError(msg, x.__class__.__name__, x.args)
                result[section][option] = value
        return result
    cherrypy.lib.reprconf.Parser.as_dict = new_as_dict

    class Root(object):
        @cherrypy.expose
        def index(self):
            return 'Nothing here'

    instance = LdapCherry()
    if context_root != '/':
        root= cherrypy.tree.mount(Root())
    app = cherrypy.tree.mount(instance, context_root, configfile)
    cherrypy.config.update(configfile)
    instance.reload(app.config, debug)

    engine = cherrypy.engine

    # Turn off autoreload
    cherrypy.config.update({'engine.autoreload.on': False})

    if environment is not None:
        cherrypy.config.update({'environment': environment})

    # Only daemonize if asked to.
    if daemonize:
        # Don't print anything to stdout/sterr.
        cherrypy.config.update({'log.screen': False})
        plugins.Daemonizer(engine).subscribe()

    if pidfile:
        plugins.PIDFile(engine, pidfile).subscribe()

    if hasattr(engine, "signal_handler"):
        engine.signal_handler.subscribe()
    if hasattr(engine, "console_control_handler"):
        engine.console_control_handler.subscribe()

    if (fastcgi and (scgi or cgi)) or (scgi and cgi):
        cherrypy.log.error("You may only specify one of the cgi, fastcgi, and "
                           "scgi options.", 'ENGINE')
        sys.exit(1)
    elif fastcgi or scgi or cgi:
        # Turn off the default HTTP server (which is subscribed by default).
        cherrypy.server.unsubscribe()

        addr = cherrypy.server.bind_addr
        if fastcgi:
            f = servers.FlupFCGIServer(application=cherrypy.tree,
                                       bindAddress=addr)
        elif scgi:
            f = servers.FlupSCGIServer(application=cherrypy.tree,
                                       bindAddress=addr)
        else:
            f = servers.FlupCGIServer(application=cherrypy.tree,
                                      bindAddress=addr)
        s = servers.ServerAdapter(engine, httpserver=f, bind_addr=addr)
        s.subscribe()

    # Always start the engine; this will start all other services
    try:
        engine.start()
    except Exception as e:
        # Assume the error has been logged already via bus.log.
        sys.exit(1)
    else:
        engine.block()


def main():
    from optparse import OptionParser

    p = OptionParser()
    p.add_option('-c', '--config', dest='config',
                 help="specify config file")
    p.add_option('-d', action="store_true", dest='daemonize',
                 help="run the server as a daemon")
    p.add_option('-e', '--environment', dest='environment', default=None,
                 help="apply the given config environment")
    p.add_option('-f', action="store_true", dest='fastcgi',
                 help="start a fastcgi server instead"
                 " of the default HTTP server")
    p.add_option('-s', action="store_true", dest='scgi',
                 help="start a scgi server instead of the default HTTP server")
    p.add_option('-x', action="store_true", dest='cgi',
                 help="start a cgi server instead of the default HTTP server")
    p.add_option('-p', '--pidfile', dest='pidfile', default=None,
                 help="store the process id in the given file")
    p.add_option('-P', '--Path', action="append", dest='Path',
                 help="add the given paths to sys.path")
    p.add_option('-D', '--debug', action="store_true", dest='debug',
                 help="debug to stderr in foreground")
    options, args = p.parse_args()

    if options.Path:
        for p in options.Path:
            sys.path.insert(0, p)

    if options.config is None:
        print('-c|--config <path/to/config/file> is mandatory')
        exit(1)

    if not os.path.isfile(options.config):
        print('configuration file "' + options.config + '" doesn\'t exist')
        exit(1)
    
    context_root='/'
    try:
        config = configparser.ConfigParser()
        config.read(options.config)
        context_root=config['global'].get('context_root','"/"')[1:-1]
        print(context_root)
    except Exception as e:
        print("something wrong with config file",str(e))
        exit(1)

    start(options.config, options.daemonize,
          options.environment, options.fastcgi, options.scgi,
          options.pidfile, options.cgi, options.debug,context_root)


if __name__ == '__main__':
    main()
