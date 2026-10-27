# lris2

LRIS2 Instrument Control Software

## Structure

- `daemons/` – libby hardware daemons, one script per device type
- `config/` – one YAML per daemon instance, named for its `peer_id`
- `systemd/` – per-instance env files and the host setup script
- `grafana/` – Grafana dashboards, imported on meridian
- `gui/` – Graphical interfaces (`slitmaskgui`, `demo`)
- `scripts/` – AIT and utility scripts
- `src/driver/` – Hardware driver submodules
- `tests/` – Unit tests

## Quick start

```bash
# 1) Clone
git clone <repo-url>
cd lris2

# 2) Make sure submodule URLs are in sync
git submodule sync --recursive
git submodule update --init --recursive

# 3) Create the environment and install, editable
uv sync --all-packages --extra dev
```

`--all-packages` matters: the drivers under `src/driver/` are uv workspace
members, and a plain `uv sync` installs only this package's own dependencies.
Run commands through `uv run <command>`. Instrument hosts install with
`systemd/install.sh` instead; see [`systemd/README.md`](systemd/README.md).

## The camera daemon

`daemons/camera` serves the Archon as `lris2.rcam`: the generic camera
keywords, every declared bias channel, and the HeaterX setpoints and
temperatures. It needs more than the other daemons, since it drives camerad
in-process rather than over a socket:

```bash
uv sync --all-packages --extra camera    # builds the camera_interface module too
uv run daemons/camera -c config/r/rcam.yaml
```

On a deployed host it runs as a service and both checkouts live under
`/opt/lris2`; see [`systemd/README.md`](systemd/README.md).

Reading does not need the detector powered. Opening the link is enough:

```bash
libby modify lris2.rcam.isopen true
libby show "lris2.rcam.%"
```

A keyword write needs `loadfirmware` first, so the controller holds the
configuration camerad parsed; a write patches a single configuration line and
the line numbers have to agree. The controller also refuses to apply a bias
change while the detector is unpowered.

`config/r/rcam.yaml` names every channel that gets a keyword, and carries
the voltage limits for the four module 4 rails that have them.

## Submodules

This repo uses submodules under `src/driver/`:

| Submodule | Path | Import |
|-----------|------|--------|
| coo-ethercat | `src/driver/coo_ethercat` | `lris2.driver.coo_ethercat` |
| lris2-csu | `src/driver/lris2_csu` | `lris2.driver.lris2_csu` |
| pdu | `src/driver/pdu` | `lris2.driver.pdu.src` |
| sunpower | `src/driver/sunpower` | `lris2.driver.sunpower` |

### Pull the submodules

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### Update to the latest on a tracked branch (e.g., main)

> Only do this if you intend to move submodule pointers and commit them.

```bash
# One-off refresh to submodules' tracked branches
git submodule update --remote --merge --recursive

# Record updated pointers in parent repo
git add .gitmodules .
git commit -m "Update submodules to latest on main"
```

## Running the daemons

Each daemon takes its config with `-c` and serves keywords over libby
(RabbitMQ by default), addressed as `lris2.<peer_id>.<keyword>`:

```bash
daemons/vacuum-gauge -c config/lris2_rpress.yaml
libby show lris2.rpress.pressure1
```

The `libby` CLI reads `~/.libby/cli_config.yaml`; on the instrument host it
needs only:

```yaml
transport: rabbitmq
rabbitmq_url: amqp://localhost
```

The PDUs are the exception: like hispec's `hspower`, they form their own
group, `l2power`, one peer per PDU. `daemons/l2power/` holds a shared base
and one script per PDU family:

```bash
uv run daemons/l2power/eaton_pdu -c config/l2power/l2power_pdu1.yaml
libby modify l2power.pdu1.state3 false
```

For running daemons as services, see [`systemd/README.md`](systemd/README.md).

## Testing

Tests mirror the `src/` layout under `tests/`.

To run tests from the project root:

```bash
pytest
```

## Contributing

1. Create a feature branch.
2. Include tests for new behavior.
3. Run `pytest` before opening a PR.