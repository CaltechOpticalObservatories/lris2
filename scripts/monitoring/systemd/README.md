# Switching telemetry sources

Two ways to get Archon telemetry into InfluxDB:

- **Old**: `lris2-archon-collector.service` (direct camerad connection)
- **New**: `lris2-camera-interface-daemon.service` + `lris2-camera-telemetry-shipper.service`

They're currently deployed to run **side by side** (both write the same
measurements) until we're ready to cut over. When ready:

```
sudo systemctl disable --now lris2-archon-collector
```

To roll back to the old path instead:
```
sudo systemctl disable --now lris2-camera-interface-daemon lris2-camera-telemetry-shipper
sudo systemctl enable --now lris2-archon-collector
```

At actual cutover, also add `Conflicts=lris2-archon-collector.service` (+
ordering) back into the two new unit files, so future starts of the new path
can't accidentally run alongside the old one again.
