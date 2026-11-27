# AAIF Project Proposal — sources-lib

> Draft for submission via https://github.com/aaif/project-proposals/issues/new?template=project-proposal.yml
> Issue title: `[Project Proposal] sources-lib`

---

## 1. Project Name

sources-lib

---

## 2. Project Description

sources-lib is a Rust crate that provides a uniform `SourceAdapter` protocol over heterogeneous data sources — files, shell, HTTP polling, Git, GitHub, databases, directories, metrics, MCP servers, and A2A agents — with a JSON-RPC 2.0 M2M interface and an Axum-based HTTP control plane.

Its primary value is **polyglot interoperability**: it ships as a standalone binary (no Python runtime required on the target host), enabling Go, Rust, C++, Java, and any other language runtime to consume a full adapter ecosystem over HTTP/JSON-RPC without embedding a language-specific SDK. This fills a gap that MCP and existing adapter libraries leave open — they assume Python or TypeScript as the host language.

The project originated as the integration layer inside the URACE autonomous agent runtime and was extracted as a standalone library when the polyglot use case became clear.

---

## 3. Preferred Lifecycle Stage

**Sandbox**

---

## 4. Alignment with AAIF Mission

sources-lib directly addresses AAIF's interoperability mandate. Agentic systems today are fragmented by language: MCP SDKs exist for Python and TypeScript; Go, Rust, and C++ teams have no standard way to plug into the same adapter ecosystem. sources-lib provides a language-neutral wire protocol (JSON-RPC 2.0 over HTTP) and a standalone binary distribution model that any runtime can adopt without language-specific SDK work.

It also integrates A2A and MCP as first-class adapter kinds, meaning it acts as a bridge layer between the two protocols AAIF already hosts — enabling agents built on either protocol to source data through a single registry.

---

## 5. Relation to Existing AAIF Projects

| AAIF Project | Relationship |
|---|---|
| **MCP** | sources-lib includes an `mcp_server` adapter kind (Q1 2027 roadmap). It treats MCP servers as data sources within the registry, making MCP accessible to non-Python runtimes without the Python MCP SDK. |
| **A2A** | sources-lib includes an `a2a` adapter kind today. A2A agents are first-class sources alongside files and databases. |
| **agentgateway** | Complementary — agentgateway handles routing between agents; sources-lib handles the data/tool input layer feeding those agents. |
| **AGENTS.md** | No overlap. |

sources-lib does not compete with any accepted AAIF project. It sits one layer below agent routing (agentgateway) and one layer above raw protocol SDKs (MCP, A2A).

---

## 6. Example Use Cases and Evidence of Adoption

**Use cases:**

1. **Rust AI agent runtime (URACE)** — sources-lib is the integration layer inside the URACE autonomous agent runtime. URACE executors query file, shell, Git, and HTTP sources through the registry without any Python dependency.

2. **Go backend consuming GitHub + database sources** — a Go service spawns the sources-lib binary as a sidecar and calls `POST /sources/{id}/sync` over HTTP to pull structured records from GitHub issues and a Postgres database, without writing adapter code.

3. **Polyglot MCP bridge** — a C++ inference server uses the sources-lib binary to access MCP tool servers via the `mcp_server` adapter, making MCP's 3,000+ server ecosystem available without the Python MCP SDK.

**Adoption:** The project is early-stage (Sandbox). Current known users: URACE (the originating project). External adoption is the primary goal of the next two quarters. The binary distribution model and language-neutral wire protocol are designed specifically to lower the adoption barrier for non-Python teams.

---

## 7. Technical Committee Sponsor

Not yet identified.

---

## 8. GitHub Repository URL

https://github.com/joaoalbertocsjunior/sources

---

## 9. License

Apache-2.0

---

## 10. Governance Model

The project follows [Linux Foundation Minimum Viable Governance (MVG)](https://github.com/github/MVG). Governance is documented in [GOVERNANCE.md](https://github.com/joaoalbertocsjunior/sources/blob/main/GOVERNANCE.md).

---

## 11. CI/CD & Release Workflow

CI is in progress (GitHub Actions, Q2 2027 roadmap). Current state: `cargo build` and `cargo test` run locally on every change. Releases are tagged on `main` via GitHub Releases. CI target: build + test on Linux x86_64, macOS arm64, and Windows x86_64 on every PR.

---

## 12. Public-Facing Contribution Process

Documented in [CONTRIBUTING.md](https://github.com/joaoalbertocsjunior/sources/blob/main/CONTRIBUTING.md). All contributions via pull request; at least one maintainer approval required to merge.

---

## 13. Publicly Accessible Issue Tracker

https://github.com/joaoalbertocsjunior/sources/issues

---

## 14. External Project Dependencies

| Dependency | License |
|---|---|
| tokio | MIT |
| axum | MIT |
| serde / serde_json / serde_yaml | MIT / Apache-2.0 |
| reqwest | MIT / Apache-2.0 |
| sqlx | MIT / Apache-2.0 |
| git2 (libgit2) | MIT (libgit2: GPL-2 with linking exception) |
| thiserror | MIT / Apache-2.0 |
| async-trait | MIT / Apache-2.0 |
| uuid | MIT / Apache-2.0 |
| dashmap | MIT |
| parking_lot | MIT / Apache-2.0 |
| tracing | MIT |
| tower / tower-http | MIT |

All dependencies are permissively licensed. The libgit2 linking exception permits static linking in Apache-2.0 binaries.

---

## 15. Maintainers & Contributors

| Name | GitHub | Affiliation | Role |
|---|---|---|---|
| João Alberto Cambauva dos Santos Junior | [@joaoalbertocsjunior](https://github.com/joaoalbertocsjunior) | URACE | Lead maintainer |

Contribution activity: https://github.com/joaoalbertocsjunior/sources/commits/main

---

## 16. Leadership Team & Decision Process

Single lead maintainer at this stage. Decisions are made via GitHub issues and pull requests. Significant changes (new adapters, breaking API changes) require a proposal issue open for 7 days before merging. See [GOVERNANCE.md](https://github.com/joaoalbertocsjunior/sources/blob/main/GOVERNANCE.md).

---

## 17. Lifecycle Stage Evidence (Sandbox)

**Thesis:**

sources-lib targets a specific, unserved segment: AI agent teams whose runtime is not Python or TypeScript. Today, integrating MCP or A2A into a Go or Rust agent means either: (a) shipping a Python subprocess with its full dependency tree, (b) reimplementing adapters from scratch, or (c) skipping structured source integration entirely. All three are costly or limiting.

The standalone binary model — a single self-contained executable exposing a JSON-RPC 2.0 + REST interface — eliminates that cost. Any language that can spawn a subprocess and make an HTTP call can use the full adapter ecosystem immediately.

**What would justify Growth graduation:**
- At least 3 external projects using sources-lib in production
- Published to crates.io with active download growth
- At least one additional maintainer not affiliated with the originating project

**Early external interest:** The URACE runtime (the originating project) validates the use case. The MCP and A2A adapter integrations are designed to make sources-lib useful to teams already in the AAIF ecosystem without additional protocol work.

**Public roadmap:** [ROADMAP.md](https://github.com/joaoalbertocsjunior/sources/blob/main/ROADMAP.md)

---

## 18. Security

No OpenSSF badge yet. Current security posture: no network-facing services in the library core (HTTP server is opt-in); bearer token authentication on M2M and HTTP control plane endpoints; no credentials stored or logged; dependencies auditable via `cargo audit`. Security issues should be reported via GitHub private vulnerability reporting.

---

## 19. Website URL

https://github.com/joaoalbertocsjunior/sources

> No separate documentation site yet — Q1 2027 roadmap item.

---

## 20. Documented Governance Practices

[GOVERNANCE.md](https://github.com/joaoalbertocsjunior/sources/blob/main/GOVERNANCE.md)

---

## 21. Social Media Accounts

None.

---

## 22. Trademark and Accounts

- [x] If the project is accepted, I agree to transfer all project trademarks and accounts to the Linux Foundation under the contribution agreement.

---

## 23. Existing Financial Sponsorship

None.

---

## 24. Infrastructure Needs or Requests

None at Sandbox stage.

---

## 25. Additional Information

sources-lib was extracted from the URACE runtime specifically to be a standalone, reusable, language-agnostic foundation layer. The design decision to expose everything over JSON-RPC 2.0 and HTTP — rather than a Rust-native API only — was made from the start with polyglot adoption in mind. The AAIF ecosystem (MCP, A2A) is the natural home for this project given its direct integrations with both protocols.

---

## 26. Application Contact

João Alberto Cambauva dos Santos Junior — joaoalbertocsjunior@gmail.com

---

## 27. Contributing Entity Signatory

| Name | Country | Email address |
|---|---|---|
| João Alberto Cambauva dos Santos Junior | Brazil | joaoalbertocsjunior@gmail.com |
