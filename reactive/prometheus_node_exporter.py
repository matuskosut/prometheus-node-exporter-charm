import os
from shutil import copyfile
from subprocess import call

from charms.reactive import (
    when,
    hook,
    when_not,
    set_state,
)
from charms.reactive.relations import endpoint_from_flag, endpoint_from_name
from charms.reactive.flags import clear_flag

from charmhelpers.core.hookenv import (
    config,
    resource_get,
    status_set,
    open_port,
    log,
)
from charmhelpers.core.templating import render

from charms.layer.prometheus_node_exporter import (
    start_restart,
    NODE_EXPORTER_BIN,
    NODE_EXPORTER_SERVICE,
)


@when_not('prometheus.node.exporter.bin.available')
def install_prometheus_exporter_resource():
    go_bin = resource_get('node-exporter')
    if os.path.exists(NODE_EXPORTER_BIN):
        os.remove(NODE_EXPORTER_BIN)
    copyfile(go_bin, NODE_EXPORTER_BIN)
    call('chmod +x {}'.format(NODE_EXPORTER_BIN).split())
    set_state('prometheus.node.exporter.bin.available')


@when('prometheus.node.exporter.bin.available')
@when_not('prometheus.node.exporter.systemd.available')
def render_systemd_config():
    if os.path.exists(NODE_EXPORTER_SERVICE):
        os.remove(NODE_EXPORTER_SERVICE)
    ctxt = {'port': config('port')}
    render('node-exporter.service.tmpl', NODE_EXPORTER_SERVICE, context=ctxt)
    set_state('prometheus.node.exporter.systemd.available')


@when('prometheus.node.exporter.bin.available',
      'prometheus.node.exporter.systemd.available')
@when_not('prometheus.node.exporter.available')
def set_prometheus_node_exporter_available():
    start_restart('node-exporter')
    open_port(config('port'))
    status_set("active",
               "Node-Exporter Running on port {}".format(config('port')))
    set_state('prometheus.node.exporter.available')


@when('config.changed.port',
      'prometheus.node.exporter.available')
def port_changed():
    prometheus = endpoint_from_name('scrape')
    log("Port changed, telling relations. ({})".format(config('port')))
    prometheus.configure(port=config('port'))


@when('prometheus.node.exporter.available',
      'endpoint.scrape.available')
@when_not('prometheus.node.exporter.told_port')
def set_provides_data():
    prometheus = endpoint_from_flag('endpoint.scrape.available')
    log("Scrape Endpoint became available. Telling port. ({})".format(config('port')))
    prometheus.configure(port=config('port'))
    set_state('prometheus.node.exporter.told_port')


@when_not('endpoint.scrape.available')
@when('prometheus.node.exporter.told_port')
def prometheus_left():
    log("Scrape Endpoint became unavailable")
    clear_flag('prometheus.node.exporter.told_port')


@hook('stop')
def cleanup():
    status_set("maintenance", "cleaning up prometheus-node-exporter")
    call('service node-exporter stop'.split())
    for f in [NODE_EXPORTER_BIN, NODE_EXPORTER_SERVICE]:
        call('rm {}'.format(f).split())
    status_set("active", "cleanup complete")
