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
LRIS2_CONFIG=<absolute path to that instance's config.yaml>
```

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

`doctor` checks the host and your account, and compares the installed unit and
polkit rule against what `install` would write now, so a host whose unit
predates a template change is reported rather than silently stale.

## Updating

`git pull` in `/opt/lris2/app` then `lris2 restart <name>`. The venv installs
the repo editable, so the daemons and the CLI both follow the checkout without
a reinstall.
