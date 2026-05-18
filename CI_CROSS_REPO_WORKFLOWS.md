# Cross-repository workflows

Repository relationships and workflow dispatch chains for the Posit container image ecosystem, including dogfooding and internal deployment paths.

For the reusable workflows that these dispatch chains call (inputs, secrets, examples), see [`CI.md`](./CI.md).

## Legend

```mermaid
graph TD
    A["Repository"] ==>|"workflow_dispatch"| B["Repository"]
    C["Repository"] -.->|"workflow_call"| D["Repository"]
    E["Repository"] -->|"push"| F[("Registry")]
    F --> I(["Environment"])
    G{{"GitHub App"}} ==> H["Repository"]
```

| Symbol | Meaning |
|---|---|
| Thick line | `workflow_dispatch` (cross-repo trigger via GitHub App) |
| Dashed line | `workflow_call` (reusable workflow in the same CI run) |
| Thin line | Direct action: push, Flux sync, or pull request merge |
| Rectangle | Repository or workflow |
| Cylinder | Registry |
| Stadium | Environment |
| Hexagon | GitHub App identity |

### GitHub Apps

| App | Installed on | Role |
|---|---|---|
| **posit-connect-projects** | `posit-dev/connect`<br/>`posit-dev/images-connect`<br/>`rstudio/helm` | Dispatches downstream from Posit Connect releases |
| **workbench-ide-release** | `posit-dev/images-workbench`<br/>`rstudio/rstudio-pro`<br/>`rstudio/helm` | Dispatches downstream from Posit Workbench releases |
| **posit-package-manager-automation** | `posit-dev/images-package-manager`<br/>`rstudio/package-manager`<br/>`rstudio/helm` | Dispatches downstream from Posit Package Manager (PPM) releases |
| **posit-platform** | `posit-dev/images-shared`<br/>`rstudio/helm` | Platform team operations, centralized dispatch |

Product GitHub Apps own the dispatch chain from product release through to Helm chart update. `posit-platform` handles platform-team-owned operations (e.g., scheduled rebuilds, cache cleanup).

## Production release flow

```mermaid
graph TD
    subgraph "Product Repos"
        CONNECT_PROD["connect"]
        WORKBENCH_PROD["rstudio-pro"]
        PPM_PROD["package-manager"]
    end

    CONNECT_PROD ==> IMG_CONNECT
    WORKBENCH_PROD ==> IMG_WORKBENCH
    PPM_PROD ==> IMG_PM

    subgraph "Image Repos"
        IMG_CONNECT["images-connect"]
        IMG_WORKBENCH["images-workbench"]
        IMG_PM["images-package-manager"]
    end

    IMG_CONNECT -.-> SHARED
    IMG_WORKBENCH -.-> SHARED
    IMG_PM -.-> SHARED

    SHARED["images-shared"]

    IMG_CONNECT --> REGISTRIES
    IMG_WORKBENCH --> REGISTRIES
    IMG_PM --> REGISTRIES

    REGISTRIES[("Docker Hub + GHCR")]

    IMG_CONNECT ==> HELM
    IMG_WORKBENCH ==> HELM
    IMG_PM ==> HELM

    HELM["helm"] --> K8S(["K8s Dogfood Sites"])
```

## Development and preview flow

```mermaid
graph TD
    subgraph "Product Repos"
        CONNECT_PROD["connect"]
        WORKBENCH_PROD["rstudio-pro"]
        PPM_PROD["package-manager"]
    end

    CONNECT_PROD ==> IMG_CONNECT
    WORKBENCH_PROD ==> IMG_WORKBENCH
    PPM_PROD ==> IMG_PM

    subgraph "Image Repos"
        IMG_CONNECT["images-connect"]
        IMG_WORKBENCH["images-workbench"]
        IMG_PM["images-package-manager"]
    end

    IMG_CONNECT -.-> SHARED
    IMG_WORKBENCH -.-> SHARED
    IMG_PM -.-> SHARED

    SHARED["images-shared"]

    IMG_CONNECT --> GHCR
    IMG_WORKBENCH --> GHCR
    IMG_PM --> GHCR

    GHCR[("GHCR")]

    GHCR --> K8S(["K8s Dogfood Sites"])
    GHCR --> FUZZBUCKET(["Fuzzbucket"])
    GHCR --> EKS_REF(["EKS Reference Architecture"])
```

## Per-product diagrams

### Connect

#### Production

```mermaid
graph TD
    subgraph connect
        SCRIPTS["release-scripts.yml<br/>publish_release.py"]
    end

    SCRIPTS ==> APP_REL{{"posit-connect-projects"}}
    APP_REL ==> REL

    subgraph images-connect
        REL["release.yml<br/><i>version</i>"]
        PROD_WF["production.yml<br/><i>dev-versions=exclude</i>"]
        CONTENT["content.yml<br/><i>matrix-versions=only</i>"]
    end

    REL -.-> PRODUCT_REL

    subgraph images-shared
        PRODUCT_REL["product-release.yml<br/><i>version</i><br/><i>images</i>"]
        SHARED["bakery-build-native.yml"]
    end

    REL -->|"PR merge"| PROD_WF
    REL -->|"PR merge"| CONTENT

    PROD_WF -.-> SHARED
    CONTENT -.-> SHARED

    PROD_WF -->|push| REGISTRIES[("Docker Hub + GHCR")]
    CONTENT -->|push| REGISTRIES

    PROD_WF ==> APP_HELM{{"posit-connect-projects"}}
    APP_HELM ==> HELM_WF

    subgraph helm
        HELM_WF["product-release.yml<br/><i>product</i><br/><i>version</i>"]
    end

    HELM_WF --> K8S(["K8s Dogfood Sites"])
```

Source files:

- [`release-scripts.yml`](https://github.com/posit-dev/connect/blob/main/.github/workflows/release-scripts.yml) (connect)
- [`release.yml`](https://github.com/posit-dev/images-connect/blob/main/.github/workflows/release.yml) (images-connect)
- [`production.yml`](https://github.com/posit-dev/images-connect/blob/main/.github/workflows/production.yml) (images-connect)
- [`content.yml`](https://github.com/posit-dev/images-connect/blob/main/.github/workflows/content.yml) (images-connect)
- [`product-release.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/product-release.yml) (images-shared)
- [`bakery-build-native.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/bakery-build-native.yml) (images-shared)
- [`product-release.yml`](https://github.com/rstudio/helm/blob/main/.github/workflows/product-release.yml) (helm)

#### Development

```mermaid
graph TD
    subgraph connect
        CI["ci.yml"]
    end

    CI ==> APP{{"posit-connect-projects"}}
    APP ==> DEV

    subgraph images-connect
        DEV["development.yml<br/><i>version</i>"]
    end

    DEV -.-> SHARED

    subgraph images-shared
        SHARED["bakery-build-native.yml<br/><i>dev-versions=only</i>"]
    end

    DEV -->|push| GHCR[("GHCR<br/>connect-preview")]
    GHCR --> K8S(["K8s Dogfood Sites"])
```

Source files:

- [`ci.yml`](https://github.com/posit-dev/connect/blob/main/.github/workflows/ci.yml) (connect)
- [`development.yml`](https://github.com/posit-dev/images-connect/blob/main/.github/workflows/development.yml) (images-connect)
- [`bakery-build-native.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/bakery-build-native.yml) (images-shared)

### Workbench

#### Production

```mermaid
graph TD
    subgraph rstudio-pro
        RELEASE_ALL["release-all.yml"]
        UPDATE_IMG["release-update-images-workbench.yml"]
        RELEASE_ALL --> UPDATE_IMG
    end

    UPDATE_IMG ==> APP_REL{{"workbench-ide-release"}}
    APP_REL ==> REL

    subgraph images-workbench
        REL["release.yml<br/><i>version</i>"]
        PROD_WF["production.yml<br/><i>dev-versions=exclude</i>"]
        SESSION["session.yml<br/><i>matrix-versions=only</i>"]
    end

    REL -.-> PRODUCT_REL

    subgraph images-shared
        PRODUCT_REL["product-release.yml<br/><i>version</i><br/><i>images</i>"]
        SHARED["bakery-build-native.yml"]
    end

    REL -->|"PR merge"| PROD_WF
    REL -->|"PR merge"| SESSION

    PROD_WF -.-> SHARED
    SESSION -.-> SHARED

    PROD_WF -->|push| REGISTRIES[("Docker Hub + GHCR")]
    SESSION -->|push| REGISTRIES

    PROD_WF ==> APP_HELM{{"workbench-ide-release"}}
    APP_HELM ==> HELM_WF

    subgraph helm
        HELM_WF["product-release.yml<br/><i>product</i><br/><i>version</i>"]
    end

    HELM_WF --> K8S(["K8s Dogfood Sites"])
```

Source files:

- [`release-all.yml`](https://github.com/rstudio/rstudio-pro/blob/main/.github/workflows/release-all.yml) (rstudio-pro)
- [`release-update-images-workbench.yml`](https://github.com/rstudio/rstudio-pro/blob/main/.github/workflows/release-update-images-workbench.yml) (rstudio-pro)
- [`release.yml`](https://github.com/posit-dev/images-workbench/blob/main/.github/workflows/release.yml) (images-workbench)
- [`production.yml`](https://github.com/posit-dev/images-workbench/blob/main/.github/workflows/production.yml) (images-workbench)
- [`session.yml`](https://github.com/posit-dev/images-workbench/blob/main/.github/workflows/session.yml) (images-workbench)
- [`product-release.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/product-release.yml) (images-shared)
- [`bakery-build-native.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/bakery-build-native.yml) (images-shared)
- [`product-release.yml`](https://github.com/rstudio/helm/blob/main/.github/workflows/product-release.yml) (helm)

#### Development

```mermaid
graph TD
    subgraph rstudio-pro
        NIGHTLY["release-nightly-test.yml"]
    end

    NIGHTLY ==> APP{{"workbench-ide-release"}}
    APP ==> DEV

    subgraph images-workbench
        DEV["development.yml<br/><i>version</i><br/><i>stream</i>"]
    end

    DEV -.-> SHARED

    subgraph images-shared
        SHARED["bakery-build-native.yml<br/><i>dev-versions=only</i>"]
    end

    DEV -->|push| GHCR[("GHCR<br/>workbench-preview<br/>workbench-session-init-preview")]
    GHCR --> K8S(["K8s Dogfood Sites"])
    GHCR --> FUZZBUCKET(["Fuzzbucket"])
    GHCR --> EKS_REF(["EKS Reference Architecture"])
```

Source files:

- [`release-nightly-test.yml`](https://github.com/rstudio/rstudio-pro/blob/main/.github/workflows/release-nightly-test.yml) (rstudio-pro)
- [`development.yml`](https://github.com/posit-dev/images-workbench/blob/main/.github/workflows/development.yml) (images-workbench)
- [`bakery-build-native.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/bakery-build-native.yml) (images-shared)

### Package Manager

#### Production

```mermaid
graph TD
    subgraph package-manager
        CI["ci.yml (publish job)"]
    end

    CI ==> APP_REL{{"posit-package-manager-automation"}}
    APP_REL ==> REL

    subgraph images-package-manager
        REL["release.yml<br/><i>version</i>"]
        PROD_WF["production.yml<br/><i>dev-versions=exclude</i>"]
    end

    REL -.-> PRODUCT_REL

    subgraph images-shared
        PRODUCT_REL["product-release.yml<br/><i>version</i><br/><i>images</i>"]
        SHARED["bakery-build-native.yml"]
    end

    REL -->|"PR merge"| PROD_WF
    PROD_WF -.-> SHARED

    PROD_WF -->|push| REGISTRIES[("Docker Hub + GHCR")]

    PROD_WF ==> APP_HELM{{"posit-package-manager-automation"}}
    APP_HELM ==> HELM_WF

    subgraph helm
        HELM_WF["product-release.yml<br/><i>product</i><br/><i>version</i>"]
    end

    HELM_WF --> K8S(["K8s Dogfood Sites"])
```

Source files:

- [`ci.yml`](https://github.com/rstudio/package-manager/blob/main/.github/workflows/ci.yml) (package-manager)
- [`release.yml`](https://github.com/posit-dev/images-package-manager/blob/main/.github/workflows/release.yml) (images-package-manager)
- [`production.yml`](https://github.com/posit-dev/images-package-manager/blob/main/.github/workflows/production.yml) (images-package-manager)
- [`product-release.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/product-release.yml) (images-shared)
- [`bakery-build-native.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/bakery-build-native.yml) (images-shared)
- [`product-release.yml`](https://github.com/rstudio/helm/blob/main/.github/workflows/product-release.yml) (helm)

#### Development

```mermaid
graph TD
    subgraph package-manager
        CI["ci.yml (publish job)"]
    end

    CI ==> APP{{"posit-package-manager-automation"}}
    APP ==> DEV

    subgraph images-package-manager
        DEV["development.yml<br/><i>version</i>"]
    end

    DEV -.-> SHARED

    subgraph images-shared
        SHARED["bakery-build-native.yml<br/><i>dev-versions=only</i>"]
    end

    DEV -->|push| GHCR[("GHCR<br/>package-manager-preview")]
    GHCR --> K8S(["K8s Dogfood Sites"])
```

Source files:

- [`ci.yml`](https://github.com/rstudio/package-manager/blob/main/.github/workflows/ci.yml) (package-manager)
- [`development.yml`](https://github.com/posit-dev/images-package-manager/blob/main/.github/workflows/development.yml) (images-package-manager)
- [`bakery-build-native.yml`](https://github.com/posit-dev/images-shared/blob/main/.github/workflows/bakery-build-native.yml) (images-shared)
