# Contract Delta: CLI Provisioning (`shiruno.cli`)

Describes the changed and new `python -m shiruno.cli` subcommands
(research.md §6). Invocation convention (`uv run python -m shiruno.cli
<subcommand> ...`) is unchanged from the existing `create-admin` command.

## New: `create-tenant`

```text
uv run python -m shiruno.cli create-tenant --name "Albertos" --slug albertos
```

| Flag | Required | Notes |
|---|---|---|
| `--name` | yes | Free-text display name. |
| `--slug` | yes | Must be unique platform-wide; no auto-derivation from `--name` (research.md §2). |

**Success**: creates a `Tenant` row with `status="active"`. Prints exactly:

```text
Tenant 'Albertos' (slug: 'albertos') created.
```

**Failure — slug already exists**: no row is created (the existing
`IntegrityError` → rollback → clear message → `SystemExit(1)` pattern,
identical in shape to `create-admin`'s duplicate-username handling):

```text
Error: a tenant with slug 'albertos' already exists.
```

No password, secret, or credential is ever involved in or printed by this
command (tenants have none).

## Changed: `create-admin`

```text
uv run python -m shiruno.cli create-admin --tenant albertos --username admin
```

| Flag | Required | Change |
|---|---|---|
| `--tenant` | **yes (new)** | Tenant **slug** — the operator never needs to know or supply an internal tenant id. |
| `--username` | yes | unchanged |
| `--password` | no | unchanged (insecure dev-only escape hatch; interactive `getpass` remains the documented default) |

**Success**: unchanged output —

```text
Administrator 'admin' created.
```

**Failure — tenant slug does not exist**: **new** failure mode; no
`Administrator` row is created:

```text
Error: no tenant with slug 'albertos' exists.
```

**Failure — username already exists**: unchanged from today.

**Unchanged guarantees**: password is still never accepted as a required
CLI argument (interactive `getpass`, no shell-history/`ps` exposure);
`--password` remains the same documented insecure escape hatch; no
password, password hash, JWT secret, or database credential is ever
printed by either command, on success or failure (FR-029).
