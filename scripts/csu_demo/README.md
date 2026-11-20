# CSU browser demo

An AIT tool, not shipped with the instrument: the webcam stream and bar
controls, laid out as in the daemon config's `placement`, per-bar charts of
drive temperature and current, and the CSU lab PDU's outlets with a switch for the drives. It drives
the bars only through `lris2.csu` and the PDU through `l2power.pdu-ethercat`, so
it runs anywhere the broker is reachable (`LIBBY_RABBITMQ_URL`).

## Install on the CSU host

It has its own venv, so `install.sh` syncing `/opt/lris2/venv` leaves it alone:

```bash
sudo uv venv /opt/lris2/csu-demo-venv
sudo uv pip install -p /opt/lris2/csu-demo-venv /opt/lris2/app/scripts/csu_demo
sudo install -m 644 /opt/lris2/app/scripts/csu_demo/lris2-csu-demo.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now lris2-csu-demo
```

It serves port 8088. Taking control needs `LRIS2_CSU_DEMO_PASSWORD` in
`/etc/lris2/secrets.env`. Re-run the `uv pip install` after pulling changes.

## Develop

```bash
uv venv && uv pip install -e ".[dev]" -e ../..
uv run pytest tests/
uv run lris2-csu-demo --sim --config ../../config/csu/csu.yaml
```
