# Contributing to sources-lib

## Getting started

```sh
git clone https://github.com/joaoalbertocsjunior/sources
cd sources
cargo build
cargo test
```

## How to contribute

- **Bug reports** — open an issue with a minimal reproduction
- **Feature requests** — open an issue before writing code; describe the use case
- **Pull requests** — fork, branch off `main`, keep changes focused, include tests

## Pull request checklist

- [ ] `cargo test` passes
- [ ] `cargo clippy -- -D warnings` passes
- [ ] New public API has doc comments
- [ ] PR description explains the why, not just the what

## Adapter contributions

New adapters live in `src/adapters/`. Each adapter must implement the `SourceAdapter` trait defined in `src/adapter.rs`. Add a unit test in the same file and register the adapter in `src/adapters/mod.rs`.

## Commit style

Use conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`. Keep the subject line under 72 characters.

## Code of conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## License

By contributing, you agree that your contributions are licensed under Apache-2.0.
