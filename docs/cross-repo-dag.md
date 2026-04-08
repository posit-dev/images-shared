# Cross-Repository Workflow DAG

Repository relationships and workflow dispatch chains for the Posit container
image ecosystem, including dogfooding and internal deployment paths.

Related issues:
- posit-dev/images-shared#279 — Consume `package-manager-preview` image in Dogfood
- posit-dev/images-shared#280 — Workbench dogfood/CI consumes preview images
- posit-dev/images-shared#219 — Automatically deploy images to K8s using Helm
- posit-dev/images-shared#302 — Add `workflow_dispatch` support to image CI workflows

## Legend

```mermaid
graph TD
    A["Repository"] -.->|"workflow_call"| B["Repository"]
    C["Repository"] -->|"push"| D["Registry / Environment"]
    E["Repository"] -.->|"workflow_dispatch (planned)"| F["Repository"]
    G["Bot 🤖"] -.->|"triggers (planned)"| H["Repository"]
```

| Symbol | Meaning |
|---|---|
| Solid line | Direct action (push, sync) |
| Dashed line | Cross-repo invocation (workflow_call, workflow_dispatch) or planned |
| `workflow_call` | Reusable workflow invocation (caller → shared) |
| `workflow_dispatch` | Cross-repo trigger via GitHub App |
| `push` | Image push to registry |
| `Flux sync` | GitOps pull from Helm chart repo |
| 🤖 | GitHub App bot identity |

### GitHub Apps

| Bot | Installed on | Role |
|---|---|---|
| **Connect Bot** 🤖 | `posit-dev/connect`, `images-connect`, `rstudio/helm` | Dispatches downstream from Connect releases |
| **Workbench Bot** 🤖 | `posit-dev/images-workbench`, `rstudio/rstudio-pro`, `rstudio/helm` | Dispatches downstream from Workbench releases |
| **PPM Bot** 🤖 | `posit-dev/images-package-manager`, `rstudio/package-manager`, `rstudio/helm` | Dispatches downstream from PPM releases |
| **Platform Bot** 🤖 | `posit-dev/images-shared`, `rstudio/helm` | Platform team operations, centralized dispatch (future) |

Product bots own the dispatch chain from product release through to Helm
chart update. The Platform Bot handles platform-team-owned operations
(e.g., scheduled rebuilds, cache cleanup). Centralized dispatch through the
Platform Bot is a future option once the per-product chains are stable.

## Production Release Flow

```mermaid
graph TD
    subgraph "Product Repos"
        CONNECT_PROD["**posit-dev/connect**"]
        WORKBENCH_PROD["**rstudio/rstudio-pro**"]
        PPM_PROD["**rstudio/package-manager**"]
    end

    CONNECT_BOT["Connect Bot 🤖"]
    WORKBENCH_BOT["Workbench Bot 🤖"]
    PPM_BOT["PPM Bot 🤖"]

    CONNECT_PROD -.-> CONNECT_BOT
    WORKBENCH_PROD -.-> WORKBENCH_BOT
    PPM_PROD -.-> PPM_BOT

    CONNECT_BOT -.->|"workflow_dispatch release.yml<br/>(version)"| IMG_CONNECT
    WORKBENCH_BOT -.->|"workflow_dispatch release.yml<br/>(version)"| IMG_WORKBENCH
    PPM_BOT -.->|"workflow_dispatch release.yml<br/>(version)"| IMG_PM

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native<br/>bakery-build<br/>product-release<br/>clean"]

    subgraph "Image Repos"
        IMG_CONNECT["**posit-dev/images-connect**<br/>production<br/>content<br/>release"]
        IMG_WORKBENCH["**posit-dev/images-workbench**<br/>production<br/>session<br/>release"]
        IMG_PM["**posit-dev/images-package-manager**<br/>production<br/>release"]
    end

    IMG_CONNECT -.->|workflow_call| SHARED
    IMG_WORKBENCH -.->|workflow_call| SHARED
    IMG_PM -.->|workflow_call| SHARED

    IMG_CONNECT -->|push| DOCKERHUB
    IMG_CONNECT -->|push| GHCR
    IMG_WORKBENCH -->|push| DOCKERHUB
    IMG_WORKBENCH -->|push| GHCR
    IMG_PM -->|push| DOCKERHUB
    IMG_PM -->|push| GHCR

    DOCKERHUB["Docker Hub"]
    GHCR["GHCR"]

    IMG_CONNECT -.->|"workflow_dispatch product-release.yml"| HELM
    IMG_WORKBENCH -.->|"workflow_dispatch product-release.yml"| HELM
    IMG_PM -.->|"workflow_dispatch product-release.yml"| HELM

    HELM["**rstudio/helm**<br/>product-release<br/>chart-releaser"]
    HELM -->|Flux sync| K8S

    K8S["K8s Dogfood Sites"]
```

## Development / Preview Flow

```mermaid
graph TD
    subgraph "Product Repos"
        CONNECT_PROD["**posit-dev/connect**"]
        WORKBENCH_PROD["**rstudio/rstudio-pro**"]
        PPM_PROD["**rstudio/package-manager**"]
    end

    CONNECT_BOT["Connect Bot 🤖"]
    WORKBENCH_BOT["Workbench Bot 🤖"]
    PPM_BOT["PPM Bot 🤖"]

    CONNECT_PROD -.-> CONNECT_BOT
    WORKBENCH_PROD -.-> WORKBENCH_BOT
    PPM_PROD -.-> PPM_BOT

    CONNECT_BOT -.->|"workflow_dispatch development.yml<br/>(version)"| IMG_CONNECT
    WORKBENCH_BOT -.->|"workflow_dispatch development.yml<br/>(version)"| IMG_WORKBENCH
    PPM_BOT -.->|"workflow_dispatch development.yml<br/>(version)"| IMG_PM

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native<br/>bakery-build"]

    IMG_CONNECT["**posit-dev/images-connect**<br/>development"]
    IMG_WORKBENCH["**posit-dev/images-workbench**<br/>development"]
    IMG_PM["**posit-dev/images-package-manager**<br/>development"]

    IMG_CONNECT -.->|workflow_call| SHARED
    IMG_WORKBENCH -.->|workflow_call| SHARED
    IMG_PM -.->|workflow_call| SHARED

    IMG_CONNECT -->|preview push| GHCR
    IMG_WORKBENCH -->|preview push| GHCR
    IMG_PM -->|preview push| GHCR

    GHCR["GHCR<br/>connect-preview<br/>workbench-preview<br/>workbench-session-init-preview<br/>package-manager-preview"]

    GHCR --> K8S
    GHCR --> FUZZBUCKET
    GHCR --> EKS_REF

    K8S["K8s Dogfood Sites"]
    FUZZBUCKET["Fuzzbucket<br/>IDE Automation"]
    EKS_REF["EKS Reference Architecture"]
```

## Connect

### Production

```mermaid
graph TD
    PROD["**posit-dev/connect**<br/>release-scripts.yml"]
    BOT["Connect Bot 🤖"]

    PROD -.-> BOT
    BOT -.->|"workflow_dispatch release.yml<br/>(version)"| IMG_RELEASE

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native<br/>product-release"]

    IMG_RELEASE["**posit-dev/images-connect**<br/>release"]
    IMG_PROD["**posit-dev/images-connect**<br/>production"]
    IMG_CONTENT["**posit-dev/images-connect**<br/>content"]

    IMG_RELEASE -.->|workflow_call| SHARED
    IMG_PROD -.->|workflow_call| SHARED
    IMG_CONTENT -.->|workflow_call| SHARED

    IMG_RELEASE -->|"merge to main"| IMG_PROD
    IMG_RELEASE -->|"merge to main"| IMG_CONTENT

    IMG_PROD -->|push| DOCKERHUB
    IMG_PROD -->|push| GHCR
    IMG_CONTENT -->|push| DOCKERHUB
    IMG_CONTENT -->|push| GHCR

    DOCKERHUB["Docker Hub<br/>rstudio/rstudio-connect<br/>rstudio/rstudio-connect-content-init"]
    GHCR["GHCR"]

    IMG_PROD -.->|"workflow_dispatch product-release.yml"| HELM
    HELM["**rstudio/helm**<br/>product-release<br/>chart-releaser"]
    HELM -->|Flux sync| K8S

    K8S["K8s Dogfood Sites"]
```

### Development

```mermaid
graph TD
    PROD["**posit-dev/connect**<br/>release-scripts.yml"]
    BOT["Connect Bot 🤖"]

    PROD -.-> BOT
    BOT -.->|"workflow_dispatch development.yml<br/>(version)"| IMG_DEV

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native"]

    IMG_DEV["**posit-dev/images-connect**<br/>development"]

    IMG_DEV -.->|workflow_call| SHARED

    IMG_DEV -->|preview push| GHCR

    GHCR["GHCR<br/>connect-preview"]

    GHCR --> K8S

    K8S["K8s Dogfood Sites"]
```

## Workbench

### Production

```mermaid
graph TD
    PROD["**rstudio/rstudio-pro**<br/>release-all.yml"]
    BOT["Workbench Bot 🤖"]

    PROD -.-> BOT
    BOT -.->|"workflow_dispatch release.yml<br/>(version)"| IMG_RELEASE

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native<br/>product-release"]

    IMG_RELEASE["**posit-dev/images-workbench**<br/>release"]
    IMG_PROD["**posit-dev/images-workbench**<br/>production"]
    IMG_SESSION["**posit-dev/images-workbench**<br/>session"]

    IMG_RELEASE -.->|workflow_call| SHARED
    IMG_PROD -.->|workflow_call| SHARED
    IMG_SESSION -.->|workflow_call| SHARED

    IMG_RELEASE -->|"merge to main"| IMG_PROD
    IMG_RELEASE -->|"merge to main"| IMG_SESSION

    IMG_PROD -->|push| DOCKERHUB
    IMG_PROD -->|push| GHCR
    IMG_SESSION -->|push| DOCKERHUB
    IMG_SESSION -->|push| GHCR

    DOCKERHUB["Docker Hub<br/>rstudio/rstudio-workbench<br/>rstudio/r-session-complete"]
    GHCR["GHCR"]

    IMG_PROD -.->|"workflow_dispatch product-release.yml"| HELM
    HELM["**rstudio/helm**<br/>product-release<br/>chart-releaser"]
    HELM -->|Flux sync| K8S

    K8S["K8s Dogfood Sites"]
```

### Development

```mermaid
graph TD
    PROD["**rstudio/rstudio-pro**<br/>release-all.yml"]
    BOT["Workbench Bot 🤖"]

    PROD -.-> BOT
    BOT -.->|"workflow_dispatch development.yml<br/>(version)"| IMG_DEV

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native"]

    IMG_DEV["**posit-dev/images-workbench**<br/>development"]

    IMG_DEV -.->|workflow_call| SHARED

    IMG_DEV -->|preview push| GHCR

    GHCR["GHCR<br/>workbench-preview<br/>workbench-session-init-preview"]

    GHCR --> K8S
    GHCR --> FUZZBUCKET
    GHCR --> EKS_REF

    K8S["K8s Dogfood Sites"]
    FUZZBUCKET["Fuzzbucket<br/>IDE Automation"]
    EKS_REF["EKS Reference Architecture"]
```

## Package Manager

### Production

```mermaid
graph TD
    PROD["**rstudio/package-manager**<br/>ci.yml (tag push)"]
    BOT["PPM Bot 🤖"]

    PROD -.-> BOT
    BOT -.->|"workflow_dispatch release.yml<br/>(version)"| IMG_RELEASE

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native<br/>product-release"]

    IMG_RELEASE["**posit-dev/images-package-manager**<br/>release"]
    IMG_PROD["**posit-dev/images-package-manager**<br/>production"]

    IMG_RELEASE -.->|workflow_call| SHARED
    IMG_PROD -.->|workflow_call| SHARED

    IMG_RELEASE -->|"merge to main"| IMG_PROD

    IMG_PROD -->|push| DOCKERHUB
    IMG_PROD -->|push| GHCR

    DOCKERHUB["Docker Hub<br/>rstudio/rstudio-package-manager"]
    GHCR["GHCR"]

    IMG_PROD -.->|"workflow_dispatch product-release.yml"| HELM
    HELM["**rstudio/helm**<br/>product-release<br/>chart-releaser"]
    HELM -->|Flux sync| K8S

    K8S["K8s Dogfood Sites"]
```

### Development

```mermaid
graph TD
    PROD["**rstudio/package-manager**<br/>ci.yml (tag push)"]
    BOT["PPM Bot 🤖"]

    PROD -.-> BOT
    BOT -.->|"workflow_dispatch development.yml<br/>(version)"| IMG_DEV

    SHARED["**posit-dev/images-shared**<br/>bakery-build-native"]

    IMG_DEV["**posit-dev/images-package-manager**<br/>development"]

    IMG_DEV -.->|workflow_call| SHARED

    IMG_DEV -->|preview push| GHCR

    GHCR["GHCR<br/>package-manager-preview"]

    GHCR --> K8S

    K8S["K8s Dogfood Sites"]
```

## Repositories Involved in Deployment

| Repository | Role | Deploy Target |
|---|---|---|
| `posit-dev/images-connect` | Build Connect images | Docker Hub, GHCR |
| `posit-dev/images-workbench` | Build Workbench images | Docker Hub, GHCR |
| `posit-dev/images-package-manager` | Build PPM images | Docker Hub, GHCR |
| `posit-dev/images-shared` | Shared build workflows | — |
| `rstudio/helm` | Helm charts for all products | K8s dogfood (Flux) |
| `rstudio/helm-package-manager` | Legacy PPM Helm chart (retiring) | K8s dogfood (Flux) |

### External Repos (Product Source)

| Repository | Trigger Mechanism |
|---|---|
| `posit-dev/connect` | `publish_release.py` dispatches downstream |
| `rstudio/rstudio-pro` | `release-all.yml` dispatches sub-workflows |
| `rstudio/package-manager` | Tag push triggers `ci.yml` publish job |

### Internal Environments

| Environment | Consumes | Source |
|---|---|---|
| K8s Dogfood | PPM preview, Workbench preview, Helm charts | GHCR, Flux |
| Fuzzbucket | Workbench session images | GHCR |
| EKS Reference Architecture | Workbench images | GHCR |
