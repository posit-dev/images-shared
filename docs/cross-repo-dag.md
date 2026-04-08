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
    A["Repository"] -->|"workflow_call"| B["Repository"]
    C["Repository"] -->|"push"| D["Registry / Environment"]
    E["Repository"] -.->|"workflow_dispatch (planned)"| F["Repository"]
    G["Bot 🤖"] -.->|"triggers (planned)"| H["Repository"]
```

| Symbol | Meaning |
|---|---|
| Solid line | Active today |
| Dashed line | Planned / in progress |
| `workflow_call` | Reusable workflow invocation (same run) |
| `workflow_dispatch` | Cross-repo trigger via GitHub App |
| `push` | Image push to registry |
| `Flux sync` | GitOps pull from Helm chart repo |
| 🤖 | GitHub App bot identity |

### GitHub Apps

| Bot | Scope | Role |
|---|---|---|
| **Connect Bot** 🤖 | `posit-dev/connect` | Dispatches downstream from Connect releases |
| **Workbench Bot** 🤖 | `rstudio/rstudio-pro` | Dispatches downstream from Workbench releases |
| **PPM Bot** 🤖 | `rstudio/package-manager` | Dispatches downstream from PPM releases |
| **Platform Bot** 🤖 | `posit-dev/images-*`, `rstudio/helm` | Platform team operations, centralized dispatch (future) |

Product bots own the dispatch chain from product release through to Helm
chart update. The Platform Bot handles platform-team-owned operations
(e.g., scheduled rebuilds, cache cleanup). Centralized dispatch through the
Platform Bot is a future option once the per-product chains are stable.

## Production Release Flow

```mermaid
graph TD
    subgraph "Product Repos"
        CONNECT_PROD["posit-dev/connect"]
        WORKBENCH_PROD["rstudio/rstudio-pro"]
        PPM_PROD["rstudio/package-manager"]
    end

    CONNECT_BOT["Connect Bot 🤖"]
    WORKBENCH_BOT["Workbench Bot 🤖"]
    PPM_BOT["PPM Bot 🤖"]

    CONNECT_PROD -.-> CONNECT_BOT
    WORKBENCH_PROD -.-> WORKBENCH_BOT
    PPM_PROD -.-> PPM_BOT

    CONNECT_BOT -.->|"workflow_dispatch release.yml"| IMG_CONNECT
    WORKBENCH_BOT -.->|"workflow_dispatch release.yml"| IMG_WORKBENCH
    PPM_BOT -.->|"workflow_dispatch release.yml"| IMG_PM

    subgraph "Image Repos"
        IMG_CONNECT["posit-dev/images-connect<br/>production · content · release"]
        IMG_WORKBENCH["posit-dev/images-workbench<br/>production · session · release"]
        IMG_PM["posit-dev/images-package-manager<br/>production · release"]
    end

    IMG_CONNECT -->|workflow_call| SHARED
    IMG_WORKBENCH -->|workflow_call| SHARED
    IMG_PM -->|workflow_call| SHARED

    SHARED["posit-dev/images-shared<br/>bakery-build-native · bakery-build<br/>product-release · clean"]

    IMG_CONNECT -->|push| DOCKERHUB
    IMG_CONNECT -->|push| GHCR
    IMG_WORKBENCH -->|push| DOCKERHUB
    IMG_WORKBENCH -->|push| GHCR
    IMG_PM -->|push| DOCKERHUB
    IMG_PM -->|push| GHCR

    DOCKERHUB["Docker Hub"]
    GHCR["GHCR"]

    CONNECT_BOT -.->|"workflow_dispatch product-release.yml"| HELM
    WORKBENCH_BOT -.->|"workflow_dispatch product-release.yml"| HELM
    PPM_BOT -.->|"workflow_dispatch product-release.yml"| HELM

    HELM["rstudio/helm<br/>product-release · chart-releaser"]
    HELM -->|Flux sync| K8S

    K8S["K8s Dogfood Sites"]
```

## Development / Preview Flow

```mermaid
graph TD
    IMG_CONNECT["posit-dev/images-connect<br/>development"]
    IMG_WORKBENCH["posit-dev/images-workbench<br/>development"]
    IMG_PM["posit-dev/images-package-manager<br/>development"]

    IMG_CONNECT -->|workflow_call| SHARED
    IMG_WORKBENCH -->|workflow_call| SHARED
    IMG_PM -->|workflow_call| SHARED

    SHARED["posit-dev/images-shared<br/>bakery-build-native · bakery-build"]

    IMG_CONNECT -->|preview push| GHCR
    IMG_WORKBENCH -->|preview push| GHCR
    IMG_PM -->|preview push| GHCR

    GHCR["GHCR<br/>connect-preview<br/>workbench-preview<br/>package-manager-preview"]

    GHCR --> K8S
    GHCR --> FUZZBUCKET
    GHCR --> EKS_REF

    K8S["K8s Dogfood Sites"]
    FUZZBUCKET["Fuzzbucket<br/>IDE Automation"]
    EKS_REF["EKS Reference Architecture"]
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
