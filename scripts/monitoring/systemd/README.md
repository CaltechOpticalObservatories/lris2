# Switching telemetry sources

Two ways to get Archon telemetry into InfluxDB, mutually exclusive via
`Conflicts=` in the unit files (starting one stops the other, but does not
change what's `enabled` at boot — see below):

- **Old**: `lris2-archon-collector.service` (direct camerad connection)
- **New**: `lris2-camera-interface-daemon.service` + `lris2-camera-telemetry-shipper.service`

Switch to the new path:
```
sudo systemctl enable --now lris2-camera-interface-daemon lris2-camera-telemetry-shipper
sudo systemctl disable lris2-archon-collector   # so it doesn't come back on reboot
```

Switch back to the old path:
```
sudo systemctl enable --now lris2-archon-collector
sudo systemctl disable lris2-camera-interface-daemon lris2-camera-telemetry-shipper
```

`Conflicts=` stops the other side immediately either way; the `disable` in
each sequence is what makes the choice survive a reboot.
