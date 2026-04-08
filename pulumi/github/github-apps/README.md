# github-apps

Manages GitHub App installations and org-level secret sharing for the Posit
container image ecosystem.

## What this manages

- **App installations**: Which repositories each GitHub App can access
- **Org-level secrets**: Created with `visibility: selected` and shared with
  the app's repositories

## What this does NOT manage

- **GitHub App creation**: Apps must be created via the GitHub UI or API.
  Once created, add the `installationId` to the stack config.
- **Secret values**: Secret values are created as placeholders and must be
  set out-of-band via `gh secret set` or the GitHub UI. Pulumi ignores
  changes to secret values after creation.

## Apps

| App | posit-dev repos | rstudio repos |
|---|---|---|
| connect-bot | connect, images-connect | helm (app only) |
| workbench-bot | images-workbench | rstudio-pro, helm (app only) |
| ppm-bot | images-package-manager | package-manager, helm (app only) |
| platform-bot | images-shared | helm |

| Line | Meaning |
|---|---|
| **Thick** (`==>`) | App installed + secrets shared |
| **Thin** (`-->`) | App installed only |

### Full Ecosystem

```mermaid
graph TD
    CB["**Connect Bot** 🤖"]
    WB["**Workbench Bot** 🤖"]
    PB["**PPM Bot** 🤖"]
    PLB["**Platform Bot** 🤖"]

    CB ==> PCT["posit-dev/<br/>connect"]
    CB ==> IC["posit-dev/<br/>images-connect"]
    CB --> HELM["rstudio/helm"]

    WB ==> IW["posit-dev/<br/>images-workbench"]
    WB ==> RSP["rstudio/<br/>rstudio-pro"]
    WB --> HELM

    PB ==> IP["posit-dev/<br/>images-package-manager"]
    PB ==> PPM["rstudio/<br/>package-manager"]
    PB --> HELM

    PLB ==> IS["posit-dev/<br/>images-shared"]
    PLB ==> HELM
```

### Connect Bot

```mermaid
graph TD
    BOT["**Connect Bot** 🤖"]

    BOT ==> PCT["posit-dev/connect"]
    BOT ==> IC["posit-dev/images-connect"]
    BOT --> HELM["rstudio/helm"]
```

### Workbench Bot

```mermaid
graph TD
    BOT["**Workbench Bot** 🤖"]

    BOT ==> IW["posit-dev/images-workbench"]
    BOT ==> RSP["rstudio/rstudio-pro"]
    BOT --> HELM["rstudio/helm"]
```

### PPM Bot

```mermaid
graph TD
    BOT["**PPM Bot** 🤖"]

    BOT ==> IP["posit-dev/images-package-manager"]
    BOT ==> PPM["rstudio/package-manager"]
    BOT --> HELM["rstudio/helm"]
```

### Platform Bot

```mermaid
graph TD
    BOT["**Platform Bot** 🤖"]

    BOT ==> IS["posit-dev/images-shared"]
    BOT ==> HELM["rstudio/helm"]
```

## Usage

```bash
just setup
just preview posit-dev
just up posit-dev
just preview rstudio
just up rstudio
```

## Setting secret values

Secret values are managed by Pulumi, not set manually. Use `--path --secret`
to set values under each app's config:

```bash
pulumi config set --path --secret "github-apps:apps.connect-bot.secrets.APP_ID" "<app-id>"
pulumi config set --path --secret "github-apps:apps.connect-bot.secrets.APP_PRIVATE_KEY" "<pem-contents>"
```

Pulumi encrypts values in the stack config file and sends them to GitHub's
API encrypted with the org's public key. Plaintext never touches disk or logs.

The org-level secret naming convention is `{APP_NAME}_{SECRET_NAME}`,
e.g., `CONNECT_BOT_APP_ID`.

## Adding a new app

1. Create the GitHub App in the GitHub UI
2. Install it on the target org(s)
3. Add the app config to `Pulumi.{org}.yaml` with the `installationId`
4. Set secret values: `pulumi config set --path --secret "github-apps:apps.<name>.secrets.<key>" "<value>"`
5. Run `just up {org}`
