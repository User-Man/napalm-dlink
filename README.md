# napalm_dlink - `This is not complete yet`

This is a [NAPALM](https://github.com/napalm-automation/napalm) community driver for the D-Link Switch.

## Quick start
```
python setup.py sdist
pip install ./dist/napalm-dlink-0.1.1.tar.gz
```
```python
from napalm import get_network_driver

driver = get_network_driver("dlink")
device = driver(hostname='<host_ip>', username='<username>', password="<password>", optional_args = {'transport': 'telnet'})
device.open()
facts = device.get_facts()
device.close()
```

Check the full [NAPALM Docs](https://napalm.readthedocs.io/en/latest/index.html) for more detailed instructions.

### Implemented API
* open()
* close()
* is_alive()
* cli(commands_list)
* get_config(retrieve=u'all')
* get_facts()
* get_arp_table()
* get_mac_address_table() 

### Based on:
* [napalm](https://github.com/napalm-automation/napalm)
* [napalm-ce](https://github.com/napalm-automation-community/napalm-ce)