# Project State: India-Specific POI Conflation

**Document Purpose:** Persistent state and decision log tracking repository progress, environment baselines, technical decisions, and planned milestones.

---

## 1. Current Milestone

- **Milestone:** Milestone 1 — Feasibility and Environment
- **Status:** In Progress (Repository Foundation & Environment Verification)
- **Target City:** Pending selection (to be determined in Milestone 2 based on OSM and Overture data coverage)

---

## 2. Verified Environment & Hardware Baseline

All values recorded below are derived directly from system execution logs on 2026-11-17:

| Dimension | Parameter | Verified Value | Source / Verification Method |
| :--- | :--- | :--- | :--- |
| **System** | Platform / OS | macOS (Darwin) | Verified via `system_profiler` / `uname -m` |
| **Hardware** | Processor Chip | Apple M3 | `system_profiler SPHardwareDataType` |
| **Hardware** | Architecture | `arm64` | `uname -m` |
| **Hardware** | Physical Memory | 8 GB RAM | `system_profiler SPHardwareDataType` |
| **Storage** | Available Disk Space | ~157 GiB free (out of 460 GiB, 64% used) | `df -h ~` |
| **Tooling** | Python Version | Python 3.14.3 | `python3 --version` |
| **Tooling** | Python Binary Path | `/opt/homebrew/bin/python3` | `which python3` |
| **Tooling** | Git Version | git version 2.47.0 | `git --version` |
| **Repository** | Working Directory | `/Users/sushantydv01/Desktop/India_Specific_POI_Conflation` | `pwd` |
| **Repository** | Active Branch | `main` | `git branch --show-current` |
| **Repository** | Remote URL | `https://github.com/sushantydv01/India_Specific_POI_Conflation.git` | `git remote -v` |
| **Git Identity**| User Name | `Sushant Yadav` | `git config user.name` |
| **Git Identity**| User Email | `sushantyadav8168@gmail.com` | `git config user.email` |

---

## 3. Milestone Progress

### Completed Tasks (Milestone 1)
- [x] Environment inspection and hardware profiling executed.
- [x] Git repository initialized with primary branch designated as `main`.
- [x] Remote tracking URL verified and linked to GitHub repository.
- [x] Existing Git committer identity (`Sushant Yadav`) verified and preserved.
- [x] Comprehensive `.gitignore` established for data engineering, Python, and geospatial workloads.
- [x] Foundational `README.md` authored detailing project goals, sources, licensing, and milestones.
- [x] Detailed project scoping document authored in `docs/project_scope.md`.
- [x] Initial repository tracking established in `PROJECT_STATE.md`.

### Pending Tasks
- [ ] Review staged initial files and verify clean repository status.
- [ ] Create initial local git commit (`chore: initialize India POI conflation project`).
- [ ] Python virtual environment and dependency strategy determination (deferred to milestone transition).
- [ ] Python 3.14 compatibility audit for geospatial libraries (e.g., Shapely, pyarrow, duckdb wheels on Apple Silicon).
- [ ] Milestone 2: Candidate Indian city evaluation and spatial data availability analysis.

---

## 4. Architecture Decisions Log (ADL)

| ID | Topic | Decision | Status | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | Git Initialization & Remote | Initialize git with default branch `main` and set `origin` to https://github.com/sushantydv01/India_Specific_POI_Conflation.git | **Approved** | Ensures standard git hygiene and preserves user identity. |
| **ADR-002** | Data Separation | Enforce strict exclusion of raw data, intermediates, and databases from version control via `.gitignore`. | **Approved** | Geospatial datasets (OSM PBFs, Overture Parquets) exceed Git capacity and must be fetched/reproduced programmatically. |
| **ADR-003** | Provisional Tech Stack | Propose DuckDB + Parquet + H3 + GeoPandas + RapidFuzz + Splink for local-first execution. | **Provisional** | Subject to environment validation and Python 3.14 wheel availability testing. No packages installed yet. |

---

## 5. Known Uncertainties & Risks

1. **Python 3.14 C-Extension / Binary Wheels:** The system environment is running Python 3.14.3. Key data engineering libraries (such as `duckdb`, `pyarrow`, `shapely`, `geopandas`, and `h3`) may or may not have pre-built stable binary wheels for Python 3.14 on macOS `arm64`, potentially requiring building from source or using a specific Python version (e.g., Python 3.11/3.12) via a virtual environment manager.
2. **Memory Constraints (8 GB RAM):** Apple M3 system has 8 GB of shared memory. Large-scale global extracts cannot be loaded directly into memory; the ingestion pipeline must strictly stream data using out-of-core columnar tools (DuckDB streaming / Parquet row-group filters / spatial bounding box predicate pushdown).
3. **Data Density & City Selection:** The balance between POI volume and computational burden will dictate the target city choice during Milestone 2.
4. **Transliteration Complexity:** India has 22 scheduled languages with extensive non-standard English phonetics; finding lightweight, high-recall phonetic matching without heavy external dependencies is an open research challenge.

---

## 6. Next Actions

1. Review and verify file accuracy across the repository.
2. Stage foundational files (`.gitignore`, `README.md`, `PROJECT_STATE.md`, `docs/project_scope.md`).
3. Execute the initial local git commit without pushing to remote.
4. Produce the final report for Milestone 1 foundation establishment.
