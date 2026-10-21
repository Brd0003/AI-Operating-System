# NornicDB — dual-homed network layout

`nornicdb-hermes-memory-gpu` is managed by an Unraid **docker template**
(`/boot/config/plugins/dockerMan/templates-user/my-nornicdb-hermes-memory-gpu.xml`),
not by compose, so its network config is not in this repo. This file records it.

## Addresses

| Network | Driver | IP | MAC | Role |
|---|---|---|---|---|
| `nestworks_docker_bridge_network` | bridge | `172.70.0.168` | `02:70:10:00:01:68` | internal; **default route** (`gw-priority=100`) |
| `br0` | macvlan | `10.70.10.168` | `02:70:10:00:01:68` | LAN; direct reachability (`gw-priority=0`) |

Both addresses serve Bolt (`7687`), HTTP/admin (`7474`) and Qdrant gRPC (`6334`).
The host port mappings `7474/7687/6334 -> 0.0.0.0` are preserved.

Consumers:

- Hermes: `NORNICDB_URI=bolt://172.70.0.168:7687`, `qdrant_grpc_uri=172.70.0.168:6334`
- Hermes appdata `.env`: `QDRANT_HOST=172.70.0.168`, `QDRANT_PORT=6334`

## Why the template uses ExtraParams

Unraid templates support exactly **one** network. `xmlToCommand()` drops its own
`--net=`/`--ip=` as soon as `<ExtraParams>` contains a `--network=` flag
(`hasNetworkParam()` in `include/Helpers.php`), so **both** networks must be declared
there and `<MyIP>`/`<MyMAC>` must be left empty (otherwise Unraid emits a stray
`--ip=` that lands on the wrong network).

`<Network>` stays `nestworks_docker_bridge_network` on purpose: the port-export branch
switches on the driver of that network, and `bridge` publishes `-p` mappings while
`macvlan` would silently convert them into `*_PORT_*` environment variables.

## Template snippet

```xml
<Network>nestworks_docker_bridge_network</Network>
<MyIP></MyIP>
<MyMAC></MyMAC>
<ExtraParams>--restart unless-stopped --network=name=nestworks_docker_bridge_network,ip=172.70.0.168,mac-address=02:70:10:00:01:68,gw-priority=100 --network=name=br0,ip=10.70.10.168,mac-address=02:70:10:00:01:68,gw-priority=0</ExtraParams>
```

## Verify

```bash
# template renders the intended command (no side effects)
php /tmp/render_cmd.php /boot/config/plugins/dockerMan/templates-user/my-nornicdb-hermes-memory-gpu.xml

docker inspect nornicdb-hermes-memory-gpu \
  --format {{range , := .NetworkSettings.Networks}}{{}}={{.IPAddress}} mac={{.MacAddress}} gwp={{.GwPriority}}{{\n}}{{end}}
# default route must stay on the bridge, not br0
docker exec nornicdb-hermes-memory-gpu cat /proc/net/route

curl -s http://10.70.10.168:7474/health          # {"status":"healthy"}
nc -z 10.70.10.168 7687 && echo bolt-ok
```

`hermes-agent` occupies `10.70.10.169` / `172.70.0.169`; `hermes-webui` was moved to
`10.70.10.171` / `172.70.0.171` so the compose stack cannot collide with either.
