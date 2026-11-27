# Building from source

## Prerequisites

- Rust stable toolchain — install via [rustup](https://rustup.rs)
- C compiler (gcc / clang / MSVC) — required by the `vendored` feature to compile libgit2 statically
- cmake — required by libgit2 vendored build

## Quick build (current platform)

```sh
cargo build --release --features vendored
```

The binary lands at `target/release/sources` (or `sources.exe` on Windows).

## Per-platform notes

### Linux x86\_64

```sh
# Ubuntu / Debian
sudo apt-get install -y build-essential cmake
cargo build --release --features vendored
```

### macOS (Apple Silicon / arm64)

```sh
# Xcode command-line tools supply clang and cmake
xcode-select --install
cargo build --release --features vendored
```

### macOS (Intel / x86\_64)

```sh
xcode-select --install
rustup target add x86_64-apple-darwin
cargo build --release --target x86_64-apple-darwin --features vendored
```

### Windows x86\_64

Install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) with the "C++ build tools" workload and [cmake](https://cmake.org/download/).

```powershell
cargo build --release --features vendored
```

## Cross-compilation

Use [`cargo-zigbuild`](https://github.com/rust-cross/cargo-zigbuild) for cross-compiling without a matching system libc:

```sh
cargo install cargo-zigbuild
rustup target add aarch64-unknown-linux-gnu
cargo zigbuild --release --target aarch64-unknown-linux-gnu --features vendored
```

## Without vendored libgit2

Omit `--features vendored` if you have libgit2 installed system-wide and want to link dynamically:

```sh
# Ubuntu / Debian
sudo apt-get install -y libgit2-dev
cargo build --release
```

Dynamic linking produces a smaller binary but requires libgit2 to be present on the target host.

## Checking the build

```sh
cargo test
cargo clippy -- -D warnings
```
