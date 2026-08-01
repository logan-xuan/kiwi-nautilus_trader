# Kiwi NautilusTrader vendor fork

This repository is the traceable Kiwi vendor fork of NautilusTrader. The
`vendor/1.231.0` branch records the exact upstream base and `kiwi/1.231` carries
the reviewed Kiwi release line. The upstream `1.231.0` version is currently an
unreleased development version, so `KIWI_FORK.json` records the exact upstream
commit instead of claiming an upstream release tag.

## Remotes and releases

```text
origin   git@github.com:logan-xuan/kiwi-nautilus_trader.git
upstream https://github.com/nautechsystems/nautilus_trader.git
```

Kiwi wheels use PEP 440 local versions such as `1.231.0+kiwi.1`. Released tags
are immutable and use `kiwi/v<version>`. A new upstream base starts a new vendor
branch; released history is never rebased or force-pushed.

## Patch policy

Integration belongs in the Kiwi Trade Node adapter. A fork patch is accepted
only when an adapter cannot provide the required behavior. Every patch must be
single-purpose, linked to an issue, covered by a regression test, and state
whether it has been submitted upstream. Portfolio, risk, OMS, broker, account,
or other Kiwi business logic must never enter this fork.

The first packaging-governance patch is tracked in the consuming Trade Node
repository because this fork has GitHub Issues disabled. Its canonical issue
reference, rationale, tests, and upstream status are recorded in
`KIWI_FORK.json`.

The `KIWI-BAR-NEXT-OPEN-001` patch adds the matching-engine primitive required
to prevent current-bar look-ahead in bar-close strategies. It implements only
generic `AT_THE_OPEN` backtest behavior; Kiwi strategy, portfolio, risk, and
result semantics remain in the Trade Node adapter. The patch will be proposed
upstream after its fork and adapter regressions are proven.

## Build policy

Only CI-built wheels from a clean checkout are consumable by Trade Node. The
wheel, SHA-256 file, build provenance, SBOM, source manifest, and license are a
single release set. Runtime environments must not import from this checkout,
modify `site-packages`, or build in an installed application directory.

This fork remains licensed under LGPL-3.0-or-later. Any external distribution
of a modified wheel must retain notices and provide the corresponding modified
source as required by that license. Commercial distribution requires a formal
license review.
