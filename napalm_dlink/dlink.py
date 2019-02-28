# -*- coding: utf-8 -*-
# Copyright 2016 Dravetech AB. All rights reserved.
#
# The contents of this file are licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

"""
Napalm driver for D-Link switch.

Read https://napalm.readthedocs.io for more information.
"""

import re
import socket
import telnetlib
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException

# import NAPALM Base
from napalm.base.base import NetworkDriver
from napalm.base.utils import py23_compat
from napalm.base.exceptions import ConnectionException

# Easier to store these as constants
HOUR_SECONDS = 3600
DAY_SECONDS = 24 * HOUR_SECONDS
WEEK_SECONDS = 7 * DAY_SECONDS
YEAR_SECONDS = 365 * DAY_SECONDS


class DLDriver(NetworkDriver):
    """NAPALM  D-Link Handler."""

    def __init__(self, hostname, username, password, timeout=60, optional_args=None):
        """NAPALM  D-Link Handler."""

        self.device = None
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.disable_paging = True
        self.platform = "dlink"
        self.profile = [self.platform]
        self.default_clipaging_status = 'enable'

        # Get optional arguments
        if optional_args is None:
            optional_args = {}

        self.inline_transfer = optional_args.get("inline_transfer", False)

        self.transport = optional_args.get("transport", "ssh")
        if self.transport == "telnet":    # Telnet only supports inline_transfer
            self.inline_transfer = True

        self.port = optional_args.get('port', 22)
        default_port = {"ssh": 22, "telnet": 23}

        # Netmiko possible arguments
        netmiko_argument_map = {
            'port': default_port[self.transport],
            'verbose': False,
            'timeout': self.timeout,
            'global_delay_factor': 1,
            'use_keys': False,
            'key_file': None,
            'ssh_strict': False,
            'system_host_keys': False,
            'alt_host_keys': False,
            'alt_key_file': '',
            'ssh_config_file': None,
            'allow_agent': False
        }
        # Build dict of any optional Netmiko args
        self.netmiko_optional_args = {
            k: optional_args.get(k, v)
            for k, v in netmiko_argument_map.items()
        }

    def _parse_output(self, output, parser_regexp):
        result_list = []
        for line in output.split("\n"):
            search_result = re.search(parser_regexp, line)
            if search_result:
                result_list.append(search_result.groupdict())
        return result_list

    @staticmethod
    def _parse_uptime(uptime_str):
        """Return the uptime in seconds as an integer."""
        (years, weeks, days, hours, minutes, seconds) = (0, 0, 0, 0, 0, 0)

        years_regx = re.search(r"(?P<year>\d+)\syear", uptime_str)
        if years_regx is not None:
            years = int(years_regx.group(1))
        weeks_regx = re.search(r"(?P<week>\d+)\sweek", uptime_str)
        if weeks_regx is not None:
            weeks = int(weeks_regx.group(1))
        days_regx = re.search(r"(?P<day>\d+)\sday", uptime_str)
        if days_regx is not None:
            days = int(days_regx.group(1))
        hours_regx = re.search(r"(?P<hour>\d+)\shour", uptime_str)
        if hours_regx is not None:
            hours = int(hours_regx.group(1))
        minutes_regx = re.search(r"(?P<minute>\d+)\sminute", uptime_str)
        if minutes_regx is not None:
            minutes = int(minutes_regx.group(1))
        seconds_regx = re.search(r"(?P<second>\d+)\ssecond", uptime_str)
        if seconds_regx is not None:
            seconds = int(seconds_regx.group(1))

        uptime_sec = (years * YEAR_SECONDS) + (weeks * WEEK_SECONDS) + (days * DAY_SECONDS) + \
                     (hours * 3600) + (minutes * 60) + seconds
        return uptime_sec

    def _get_clipaging_status(self):
        try:
            self.device.send_command("show switch", 'Next Page')
            self.device.send_command("q")  # For exit
            return 'enable'
        except IOError:
            return 'disable'

    def open(self):
        """Open a connection to the device."""
        try:
            device_type = 'cisco_ios'
            if self.transport == "telnet":
                device_type = "cisco_ios_telnet"

            self.device = ConnectHandler(device_type=device_type,
                                         host=self.hostname,
                                         username=self.username,
                                         password=self.password,
                                         **self.netmiko_optional_args)
            self.default_clipaging_status = self._get_clipaging_status()
            if self.disable_paging and self.default_clipaging_status == 'enable':
                self.device.disable_paging(command="disable clipaging")

        except NetMikoTimeoutException:
            raise ConnectionException('Cannot connect to {}'.format(self.hostname))

    def close(self):
        """Close the connection to the device."""
        if self.disable_paging and self.default_clipaging_status == 'enable':
            self.device.disable_paging(command="enable clipaging")

        self.device.disconnect()
        self.device = None

    def is_alive(self):
        """Returns a flag with the state of the connection."""
        null = chr(0)
        if self.device is None:
            return {"is_alive": False}
        if self.transport == "telnet":
            try:
                # Try sending IAC + NOP (IAC is telnet way of sending command
                # IAC = Interpret as Command (it comes before the NOP)
                self.device.write_channel(telnetlib.IAC + telnetlib.NOP)
                return {"is_alive": True}
            except UnicodeDecodeError:
                # Netmiko logging bug (remove after Netmiko >= 1.4.3)
                return {"is_alive": True}
            except AttributeError:
                return {"is_alive": False}
        else:
            # SSH
            try:
                # Try sending ASCII null byte to maintain the connection alive
                self.device.write_channel(null)
                return {"is_alive": self.device.remote_conn.transport.is_active()}
            except (socket.error, EOFError):
                # If unable to send, we can tell for sure that the connection is unusable
                return {"is_alive": False}

    def cli(self, commands):
        """
        Execute a list of commands and return the output in a dictionary format using the command
        as the key.
        """
        cli_output = dict()
        if type(commands) is not list:
            raise TypeError("Please enter a valid list of commands!")

        for command in commands:
            output = self.device.send_command(command)
            cli_output.setdefault(command, {})
            cli_output[command] = output
        return cli_output

    def get_facts(self):
        """Return a set of facts from the devices."""
        show_switch = self.device.send_command("show switch")

        switch_facts = {}
        for line in show_switch.splitlines():
            if line:
                name, value = line.split(":")
                switch_facts[name.strip()] = value.strip()

        if switch_facts.get("Device Uptime"):
            switch_facts['Device Uptime'] = self._parse_uptime(switch_facts['Device Uptime'])

        return switch_facts

    def get_config(self, retrieve='all'):
        """ Get config from device. """
        config = {
            'startup': '',
            'running': '',
            'candidate': ''
        }
        if retrieve.lower() in ('running', 'all'):
            command = 'show config current_config'
            config['running'] = py23_compat.text_type(self.device.send_command(command))
            # Some D-link switch need run other command
            if "Configuration" not in config['running']:
                command = 'show config active'
                config['running'] = py23_compat.text_type(self.device.send_command(command))
        if retrieve.lower() in ('candidate', 'all'):
            command = 'show config config_in_nvram'
            config['candidate'] = py23_compat.text_type(self.device.send_command(command))

        return config

    def get_arp_table(self):
        """
        Get arp table information.

        Sample output:
            [
                {u'interface': u'System',
                        u'ip': u'10.12.16.0',
                       u'mac': u'FF-FF-FF-FF-FF-FF',
                      u'type': u'Local/Broadcast'},
                {u'interface': u'System',
                        u'ip': u'10.12.16.1',
                       u'mac': u'00-1F-9D-48-72-51',
                      u'type': u'Dynamic'},
            ]
        """

        output = self.device.send_command('show arpentry')
        parser_regexp = ("(?P<interface>^\w+)\s+"
                         "(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+"
                         "(?P<mac>([0-9A-F]{2}[:-]){5}([0-9A-F]{2}))\s+"
                         "(?P<type>(\w+(/\w+)*))")

        return self._parse_output(output, parser_regexp)

    def get_mac_address_table(self):
        """
        Return the MAC address table.

        Sample output:
        [
        {'status': 'Forward',
             'vid': '1',
       'vlan_name': 'default',
             'mac': '00-0F-E2-21-35-20',
            'type': 'Dynamic',
            'port': '9'},

         {'status': 'Forward',
             'vid': '1',
       'vlan_name': 'default',
             'mac': '00-0F-E2-21-35-2A',
            'type': 'Dynamic',
            'port': '9'},

        {'status': 'Forward',
            'vid': '1',
      'vlan_name': 'default',
            'mac': '00-1D-E5-48-34-81',
           'type': 'Dynamic',
           'port': '9'},
        ]
        """

        output = self.device.send_command('show fdb')
        parser_regexp = ("(?P<vid>\d+)\s+"
                         "(?P<vlan_name>\w+)\s+"
                         "(?P<mac>([0-9A-F]{2}[:-]){5}([0-9A-F]{2}))\s+"
                         "(?P<port>\d+)\s+"
                         "(?P<type>\w+)\s+"
                         "(?P<status>\w+)\s+")

        return self._parse_output(output, parser_regexp)
