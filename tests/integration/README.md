# Running integration tests

Quick reference for an agent/LLM driving these tests.

## Where to run

- Integration tests need a **Kubernetes controller**, which only exists on the multipass VM
  named `ic`. The local/host machine has **no juju** — tests must run inside the VM.
- The host `projects/` folder is mounted into the VM at `~/projects/`, so any file you change
  on the host (source, tests, or a locally packed `.charm`) is visible in the VM instantly.
- VM facts: juju 3.6.x, working controller `concierge-k8s`, k8s cloud `k8s`.

## Build the charm (on the host, not the VM)

Pack locally — it's faster and the artifact shows up in the VM via the mount:

```bash
cd ~/projects/ingress-configurator-operator
charmcraft pack            # produces ingress-configurator_amd64.charm
```

## Run the tests (inside the VM)

```bash
multipass shell ic
cd ~/projects/ingress-configurator-operator
K8S_CONTROLLER=concierge-k8s tox -e integration -- \
  --charm-file=./ingress-configurator_amd64.charm \
  tests/integration/test_gateway_route.py
```

Notes:
- Target a single file (as above) or a single test with `... test_file.py::test_name`.
  Each run takes a few minutes, so prefer the narrowest target.
- Add `--keep-models` to leave models up for inspection after a run; remember to clean them up
  afterward (`juju destroy-model <name>`).

## Backend fixtures (gateway-route tests)

`test_gateway_route.py` exercises three ingress-configurator modes against one shared gateway:

- `backend_closed` — flask-k8s with its port closed (adapter, closed-ports branch).
- `backend_open` — any-charm-k8s that opens its port and serves HTTP
  (`any_charm_ingress_requirer.py`). It installs **apache2** via `charmlibs.apt` in the charm
  container and serves a known body at `/restricted`.
- `backend_integrator` — flask-k8s referenced by pod IP only (integrator mode).

The any-charm source is injected at deploy time via `--config src-overwrite=...` (loaded by a
conftest fixture), so editing `any_charm_ingress_requirer.py` does **not** require repacking the
charm — just re-run the test.
