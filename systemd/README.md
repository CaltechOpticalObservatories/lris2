# Running daemons under systemd

Operated with the `lris2` command, which comes from
[instrumentctl](https://github.com/CaltechOpticalObservatories/instrumentctl)
and is shared with the other instruments. All that is specific to LRIS2 is
`src/cli/instrument.toml`.

One template unit, `lris2@.service`, runs any `daemons/<script>` that is an
`Lris2Daemon` subclass taking `-c <config.yaml>` and blocking in
`daemon.serve()`. Each running daemon is an instance, `lris2@<name>`, backed by
an env file in `systemd/instances/`:

```sh
LRIS2_DAEMON=<path relative to daemons/, e.g. vacuum-gauge>
LRIS2_HOST=<the host it belongs on, so deploy refuses the wrong one>
```

Its config is `/etc/lris2/<name>.yaml`, deployed there from
`config/<subsystem>/<name>.yaml`.

## Host setup

Once per host, as an admin:

```bash
sudo git clone https://github.com/CaltechOpticalObservatories/lris2 /opt/lris2/app
sudo git -C /opt/lris2/app submodule update --init --recursive
sudo /opt/lris2/app/systemd/install.sh alice bob     # operators to enrol
```

`install.sh` builds the venv and hands over to `lris2 install`, which creates
the `lris2` account and the `lris2-ops` group, enrols the operators named,
makes `/etc/lris2`, `/etc/lris2/instances` and `/var/log/lris2`, seeds a
root-only `secrets.env`, and writes the template unit, the polkit rule, the
sudoers drop-in and the operator helpers. It is safe to re-run and reports only
what it changes.

Override `LRIS2_REPO_DIR`, `LRIS2_VENV_DIR` and `LRIS2_ETC_DIR` for other
paths.

## Day to day

Nothing below needs root, for anyone in `lris2-ops`:

```bash
lris2 deploy rpress        # copy its files here, enable, start
lris2 deploy --new         # every instance not deployed yet
lris2 status               # what is deployed, and is it running
lris2 restart rpress       # after editing /etc/lris2/rpress.yaml
lris2 logs rpress -f       # follow its log
lris2 doctor               # why isn't it working
```

Reading a keyword is `libby`, which `install.sh` links beside `lris2` and
wires for TAB completion through `/etc/profile.d/lris2.sh`, so it works in a
fresh login shell with nothing to set up.

Do not activate a virtualenv to use them. One holding its own editable `lris2`
shadows the deployed package while the daemons keep using `/opt/lris2/app`,
which is a confusing way to lose an afternoon.

`doctor` checks the host and your account, and compares the installed unit and
polkit rule against what `install` would write now, so a host whose unit
predates a template change is reported rather than silently stale.

## Updating

Code is an admin's to change, which is why the repo and the venv are not
writable by `lris2-ops`. An operator changes configuration and run state; the
daemons execute what an admin installed.

```bash
sudo git -C /opt/lris2/app pull
lris2 restart <name>
```

The venv installs the repo editable, so a pull alone moves the daemons and the
CLI. Only a change to the dependency list needs
`sudo /opt/lris2/venv/bin/pip install -e /opt/lris2/app` as well.

## The camera daemon's module

`rcam` is optional, like any other daemon a host may not run, so neither its
dependencies nor its module are installed by default. On a host that runs it,
`camera_interface` has to be in the venv; built per instrument, it cannot be a
dependency of this repository:

```bash
sudo git clone https://github.com/CaltechOpticalObservatories/lris2-camerad-instrument \
     /opt/lris2/camerad
sudo /opt/lris2/venv/bin/pip install -e "/opt/lris2/app[camera]"
sudo /opt/lris2/venv/bin/pip install /opt/lris2/camerad
```

`config/r/rcam.yaml` reads the camerad config from that checkout, so a pull
there moves the ACF the controller is loaded with. Without the module the
daemon still starts and serves its keywords, reporting `state: nocamera`.
