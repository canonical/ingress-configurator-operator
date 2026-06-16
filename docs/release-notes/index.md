---
myst:
  html_meta:
    "description lang=en": "History of stable releases for the Ingress Configurator charm."
---

(release_notes_index)=
# Release notes

Release notes for the `latest/stable` track of the Ingress Configurator charm, summarizing new features, bug fixes and backwards-incompatible changes in each revision.

## Release policy and schedule

This section covers the release policy and schedule for the `ingress-configurator` charm.

For any given track, we implement three different risk levels: `edge`, `candidate`, and `stable`. The release schedule for each risk level is as follows:

1. Changes pushed to the `ingress-configurator-operator` repository will be released to `edge`.
2. On Monday of every week, the current revision on `candidate` will be automatically promoted to `stable`.
3. On Monday of every week, the current revision on `edge` will be automatically promoted to `candidate`.

Both the `candidate` and `stable` promotions require approval from the maintainers. If issues are identified that might break upgrades, manual approval can be enforced to block the automatic promotion until the issues are resolved.

In special cases where an urgent fix is needed on `stable`, changes can be pushed directly to that risk level without going through the regular process.

Release notes are published for the `ingress-configurator` charm with every revision of the `latest/stable` track.

## Releases

```{toctree}
:hidden:
:maxdepth: 1
```
