# -*- coding: utf-8 -*-
"""
Add, modify, remove queues from the Common Unix Printing System
"""

import re
import logging

log = logging.getLogger(__name__)

from salt import utils


def __virtual__():
    '''
    Only load if lpadmin exists on the system
    '''
    return True if utils.which('lpadmin') else False


def printers():
    '''
    List printer destinations available on the minion system.

    Returns a hash of printer destination names and their details.

    Caveats:
        - You cannot really derive the original ppd/model from this output.

    CLI Example:

    .. code-block:: bash

        salt '*' cups.printers
    '''
    printers_long = __salt__['cmd.run']('lpstat -l -p').splitlines()
    printers = dict()
    current = None
    name = None

    for line in printers_long:
        if re.search(r"^printer\s", line):
            if current is not None:
                printers[name] = current

            current = {}
            matches = re.match(r"printer\s(\w+)\s.*(enabled|disabled)\ssince\s([^-]*)", line)
            name = matches.group(1)
            current['status'] = matches.group(2)
            current['status_age'] = matches.group(3)
            # TODO: report disabled reason

        if re.search(r"\tDescription:", line):
            current['description'] = re.match(r"\tDescription:\s(.*)", line).group(1)

        if re.search(r"\tAfter fault:", line):
            current['error_policy'] = re.match(r"\tAfter fault:\s(.*)", line).group(1)

        if re.search(r"\tLocation:", line):
            current['location'] = re.match(r"\tLocation:\s(.*)", line).group(1)

    printers[name] = current

    # Now fetch device uri
    printer_uris = __salt__['cmd.run']('lpstat -v').splitlines()

    for line in printer_uris:
        matches = re.match(r"device for ([^:]*):\s(.*)", line)
        if matches.group(1) in printers:
            printers[matches.group(1)]['uri'] = matches.group(2)
        else:
            log.warning("got uri for a printer that wasn't parsed from lpadmin: {}".format(matches.group(1)))

    return printers


def add(name, description, uri, **kwargs):
    '''
    Add/Modify a printer destination.
    Returns dictionary describing printer that was created, or False if we failed to add the printer.

    name
        The name of the destination.
        from lpstat(1) - CUPS allows printer names to contain any printable character except SPACE, TAB, "/", and "#"

    description
        The description, often presented to the end user.

    uri
        The URI of the device, which must be one of the schemes listed in `lpinfo -v`

    model
        PPD or script which will be used from the model directory. This is the normal location for drivers
        which are installed with CUPS. Alternatively you can supply a script or PPD outside of the model directory.
        This does not include the model description as printed in `lpinfo -m`, just the relative path.

    interface
        Interface script to use if model is not set.

    ppd
        PPD file to use if model is not set.

    location
        Optional physical location of the printer

    options
        PPD options

    CLI Example:

    .. code-block:: bash

        salt '*' cups.add example_printer 'Example Printer Description' 'lpd://10.0.0.1' model='drv:///sample.drv/generic.ppd' location='Office Corner'
    '''
    result = {}
    cmd = 'lpadmin -p {0} -E -D "{1}" -v "{2}"'.format(name, description, uri)

    # Can't combine model and interface/ppd
    if 'model' in kwargs:
        kwargs.pop('interface', None)
        kwargs.pop('ppd', None)
        result['model'] = kwargs['model']
        cmd += ' -m "{}"'.format(kwargs['model'])

    if 'interface' in kwargs:
        result['interface'] = kwargs['interface']
        cmd += ' -i "{}"'.format(kwargs['interface'])

    if 'ppd' in kwargs:
        result['ppd'] = kwargs['ppd']
        cmd += ' -P "{}"'.format(kwargs['ppd'])

    if 'location' in kwargs:
        result['location'] = kwargs['location']
        cmd += ' -L "{}"'.format(kwargs['location'])

    if 'options' in kwargs:
        result['options'] = kwargs['options']
        cmd += " "
        opts = ['-o {}={}'.format(k, v) for k, v in kwargs['options'].iteritems()]
        cmd += " ".join(opts)

    added = __salt__['cmd.retcode'](cmd)
    if added == 0:
        return result
    else:
        return False


def remove(name):
    '''
    Remove a printer destination

    CLI Example:

    .. code-block:: bash

        salt '*' cups.remove example_printer
    '''
    removed = __salt__['cmd.retcode']('lpadmin -x {}'.format(name))
    return removed == 0


def models():
    '''
    List models supported by the minion's cups system.

    CLI Example:

    .. code-block:: bash

        salt '*' cups.models
    '''
    return __salt__['cmd.run_stdout']('lpinfo -m')


def uris():
    '''
    List URI formats supported by the minion's cups system.

    CLI Example:

    .. code-block:: bash

        salt '*' cups.uris
    '''
    return __salt__['cmd.run_stdout']('lpinfo -v')


def options(name):
    '''
    Parse model specific options for the given printer.

    CLI Example:

    .. code-block:: bash

        salt '*' cups.options Printer_Name
    '''
    options_long = __salt__['cmd.run']('lpoptions -p {} -l'.format(name)).splitlines()

    options = list()

    for line in options_long:
        option = {}
        matches = re.match(r"([^/]+)/([^:]+):\s(.*)", line)
        option['name'] = matches.group(1)
        option['description'] = matches.group(2)
        option['values'] = list()
        option['selected'] = None

        values = matches.group(3)

        for v in values.split():
            if v[0] == '*':
                option['selected'] = v[1:]
                option['values'].append(v[1:])
            else:
                option['values'].append(v)

        options.append(option)

    return options

