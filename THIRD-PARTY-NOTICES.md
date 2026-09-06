# Third-Party Notices

SOC-IQ incorporates third-party open-source software. This document inventories the dependencies that are actually included in the shipped product — the frozen Python sidecar executable, the production frontend bundle, and the compiled Rust/Tauri desktop shell — as opposed to development- or test-only tooling.

License identifiers below are [SPDX license expressions](https://spdx.org/licenses/) taken directly from each package's own published metadata (Python `License-Expression`/classifier metadata, npm `package.json` `license` field, or the corresponding published version's license field on crates.io). No license was inferred, guessed, or assumed; every entry below is evidence-based. This document does not itself grant any license to SOC-IQ's own source code — see `LICENSE` for that. SOC-IQ's own project-owned code is licensed under the MIT License (Gate 1 closure); the third-party dependencies inventoried below remain governed exclusively by their own respective licenses as listed, and are not relicensed or affected by SOC-IQ's MIT license in any way.

This inventory reflects the dependency manifests and lockfiles present in this checkpoint as of the Gate 1 audit date. It should be regenerated whenever dependencies change.

## Scope and methodology

- **Python (backend sidecar):** `packaging/pyinstaller/socq_backend.spec` freezes `app.api.entrypoint` and explicitly excludes `PySide6` (the legacy, non-shipped desktop GUI) and all `tests/`/dev-only code. The list below is the full runtime dependency closure of the sidecar's actual production requirements (`fastapi`, `uvicorn`, `pydantic`, `rich`, `reportlab`, `requests`, `python-dotenv`, `Jinja2`, `platformdirs`, per `requirements.txt`'s own runtime/testing split), resolved from this environment's installed package metadata. Test-only packages (`pytest`, `httpx`, `pypdf`, and PySide6/the legacy GUI's dependencies) are intentionally excluded — they never ship in the frozen sidecar executable.

- **Frontend (Tauri webview bundle):** `npm ls --omit=dev --all` against the production dependency graph — `devDependencies` (build tooling, test runners, TypeScript, Vite) are excluded because they are never included in `frontend/dist`, the artifact actually bundled by Tauri.

- **Rust (Tauri desktop shell):** the full resolved dependency graphs in `src-tauri/Cargo.lock`, `keystore-core/Cargo.lock`, and `sidecar-core/Cargo.lock` — every crate a `cargo build --release` of the desktop shell actually compiles in, including transitive dependencies. `dev-dependencies` that only affect `cargo test` and are not linked into the release binary are included in the lockfiles' resolution but not distinguished separately here; none of the three crates declare any dev-dependency of note (see each `Cargo.toml`). License data was retrieved from crates.io's published metadata for each exact resolved version. This project's own three internal crates (`soc-iq`, `keystore-core`, `sidecar-core`) are excluded from this list — they are SOC-IQ's own code, not third-party.


## Frontend dependencies (production bundle)

| Package | Version | License | Source |
|---|---|---|---|
| @tauri-apps/api | 2.11.1 | Apache-2.0 OR MIT | https://github.com/tauri-apps/tauri.git |
| @tauri-apps/plugin-dialog | 2.7.2 | MIT OR Apache-2.0 | https://github.com/tauri-apps/plugins-workspace |
| @tauri-apps/plugin-fs | 2.5.1 | MIT OR Apache-2.0 | https://github.com/tauri-apps/plugins-workspace |
| cookie | 1.1.1 | MIT | jshttp/cookie |
| js-tokens | 4.0.0 | MIT | lydell/js-tokens |
| loose-envify | 1.4.0 | MIT | https://github.com/zertosh/loose-envify.git |
| react | 18.3.1 | MIT | https://github.com/facebook/react.git |
| react-dom | 18.3.1 | MIT | https://github.com/facebook/react.git |
| react-router | 7.18.2 | MIT | https://github.com/remix-run/react-router |
| react-router-dom | 7.18.2 | MIT | https://github.com/remix-run/react-router |
| scheduler | 0.23.2 | MIT | https://github.com/facebook/react.git |
| set-cookie-parser | 2.7.2 | MIT | nfriedly/set-cookie-parser |

## Python dependencies (frozen sidecar runtime)

| Package | Version | License |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.14.2 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.5.1 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| fastapi | 0.141.1 | MIT |
| h11 | 0.16.0 | MIT |
| idna | 3.19 | BSD-3-Clause |
| jinja2 | 3.1.6 | BSD License |
| markdown-it-py | 4.2.0 | MIT License |
| markupsafe | 3.0.3 | BSD-3-Clause |
| mdurl | 0.1.2 | MIT License |
| pillow | 12.3.0 | MIT-CMU |
| platformdirs | 4.9.4 | MIT |
| pydantic | 2.13.5 | MIT |
| pydantic-core | 2.46.5 | MIT |
| pygments | 2.21.0 | BSD-2-Clause |
| python-dotenv | 1.2.3 | BSD-3-Clause |
| reportlab | 5.0.1 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. |
| requests | 2.34.2 | Apache-2.0 |
| rich | 15.0.0 | MIT |
| starlette | 1.6.0 | BSD-3-Clause |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| urllib3 | 2.7.0 | MIT |
| uvicorn | 0.52.4 | BSD-3-Clause |

Note: `reportlab`'s own metadata license string is the free-text `"BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc."` rather than a plain SPDX identifier; reproduced verbatim above rather than normalized, so no license claim is invented on the project's behalf.


## Rust dependencies (compiled into the desktop shell)

540 resolved (crate, version) entries across `src-tauri`, `keystore-core`, and `sidecar-core`, covering 28 distinct license expressions. All resolved cleanly from crates.io published metadata; none required manual verification. Grouped by license below (every crate is overwhelmingly permissive MIT/Apache-2.0/BSD-family; no copyleft license was found in this dependency graph).


### (MIT OR Apache-2.0) AND Unicode-3.0 (1 crate)

unicode-ident 1.0.24


### 0BSD OR MIT OR Apache-2.0 (1 crate)

adler2 2.0.1


### Apache-2.0 (2 crates)

sync_wrapper 1.0.2, tao 0.35.3


### Apache-2.0 / MIT (1 crate)

fnv 1.0.7


### Apache-2.0 AND MIT (1 crate)

dpi 0.1.2


### Apache-2.0 OR MIT (59 crates)

async-channel 2.5.0, async-executor 1.14.0, async-fs 1.6.0, async-io 1.13.0, async-io 2.6.0, async-lock 2.8.0, async-lock 3.4.2, async-process 1.8.1, async-signal 0.2.14, async-task 4.7.1, atomic-waker 1.1.2, autocfg 1.5.1, bit-set 0.8.0, bit-vec 0.8.0, blocking 1.7.0, cargo_toml 0.22.3, concurrent-queue 2.5.0, ctor 0.8.0, ctor-proc-macro 0.0.7, dtor 0.3.0, dtor-proc-macro 0.0.6, equivalent 1.0.2, event-listener 2.5.3, event-listener 3.1.0, event-listener 5.4.2, event-listener-strategy 0.5.4, fastrand 1.9.0, fastrand 2.5.0, futures-lite 1.13.0, futures-lite 2.6.1, idna_adapter 1.2.2, indexmap 1.9.3, indexmap 2.14.0, indexmap 2.2.6, libappindicator 0.9.0, libappindicator-sys 0.9.0, muda 0.19.3, parking 2.2.1, pin-project-lite 0.2.17, polling 2.8.0, polling 3.11.0, portable-atomic 1.15.0, portable-atomic-util 0.2.7, rustc-hash 2.1.3, tauri 2.11.5, tauri-build 2.6.3, tauri-codegen 2.6.3, tauri-macros 2.6.3, tauri-plugin 2.6.3, tauri-plugin-dialog 2.7.2, tauri-plugin-fs 2.5.1, tauri-runtime 2.11.3, tauri-runtime-wry 2.11.4, tauri-utils 2.9.3, utf8_iter 1.0.4, uuid 1.25.0, waker-fn 1.2.0, window-vibrancy 0.6.0, wry 0.55.1


### Apache-2.0 WITH LLVM-exception (1 crate)

target-lexicon 0.12.16


### Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT (10 crates)

io-lifetimes 1.0.11, linux-raw-sys 0.12.1, linux-raw-sys 0.3.8, linux-raw-sys 0.4.15, rustix 0.37.28, rustix 0.38.44, rustix 1.1.4, wasi 0.11.1+wasi-snapshot-preview1, wasip2 1.0.4+wasi-0.2.12, wit-bindgen 0.57.1


### Apache-2.0/MIT (3 crates)

cesu8 1.1.0, dbus 0.9.12, libdbus-sys 0.2.7


### BSD-2-Clause OR Apache-2.0 OR MIT (2 crates)

zerocopy 0.8.56, zerocopy-derive 0.8.56


### BSD-3-Clause (4 crates)

alloc-no-stdlib 2.0.4, alloc-stdlib 0.2.4, instant 0.1.13, subtle 2.6.1


### BSD-3-Clause AND MIT (1 crate)

brotli 8.0.4


### BSD-3-Clause OR MIT OR Apache-2.0 (2 crates)

num_enum 0.7.6, num_enum_derive 0.7.6


### BSD-3-Clause/MIT (1 crate)

brotli-decompressor 5.0.3


### CC0-1.0 OR MIT-0 OR Apache-2.0 (1 crate)

dunce 1.0.5


### ISC (1 crate)

libloading 0.7.4


### MIT (111 crates)

atk 0.18.2, atk-sys 0.18.2, block2 0.6.2, bytes 1.12.1, cairo-rs 0.18.5, cairo-sys-rs 0.18.2, cargo_metadata 0.19.2, cfb 0.7.3, combine 4.6.7, darling 0.23.0, darling_core 0.23.0, darling_macro 0.23.0, derive_more 2.1.1, derive_more-impl 2.1.1, dlopen2 0.8.2, dlopen2_derive 0.4.3, dom_query 0.27.0, embed-resource 3.0.11, gdk 0.18.2, gdk-pixbuf 0.18.5, gdk-pixbuf-sys 0.18.0, gdk-sys 0.18.2, gdkwayland-sys 0.18.2, gdkx11 0.18.2, gdkx11-sys 0.18.2, generic-array 0.14.7, gio 0.18.4, gio-sys 0.18.1, glib 0.18.5, glib-macros 0.18.5, glib-sys 0.18.1, gobject-sys 0.18.0, gtk 0.18.2, gtk-sys 0.18.2, gtk3-macros 0.18.2, http-body 1.1.0, http-body-util 0.1.5, hyper 1.11.0, hyper-util 0.1.20, ico 0.5.0, infer 0.19.0, javascriptcore-rs 1.1.2, javascriptcore-rs-sys 1.1.1, libredox 0.1.20, memoffset 0.7.1, memoffset 0.9.1, mio 1.2.2, new_debug_unreachable 1.0.6, nix 0.26.4, objc2 0.6.4, objc2-encode 4.1.0, objc2-foundation 0.3.2, pango 0.18.3, pango-sys 0.18.0, phf 0.13.1, phf_codegen 0.13.1, phf_generator 0.13.1, phf_macros 0.13.1, phf_shared 0.13.1, plist 1.10.0, precomputed-hash 0.1.1, quick-xml 0.41.0, redox_syscall 0.5.18, redox_users 0.5.2, rfd 0.16.0, schemars 0.8.22, schemars 0.9.0, schemars 1.2.2, schemars_derive 0.8.22, simd-adler32 0.3.10, slab 0.4.12, soup3 0.5.0, soup3-sys 0.5.0, strsim 0.11.1, synstructure 0.13.2, tauri-winres 0.3.6, tokio 1.53.1, tokio-util 0.7.19, tower 0.5.3, tower-http 0.6.11, tower-layer 0.3.3, tower-service 0.3.3, tracing 0.1.44, tracing-attributes 0.1.31, tracing-core 0.1.36, try-lock 0.2.5, uds_windows 1.2.1, urlpattern 0.3.0, version-compare 0.2.1, vswhom 0.1.0, vswhom-sys 0.1.3, want 0.3.1, webkit2gtk 2.0.2, webkit2gtk-sys 2.0.2, webview2-com 0.38.2, webview2-com-macros 0.8.1, webview2-com-sys 0.38.2, winnow 0.5.40, winnow 0.7.15, winnow 1.0.4, winreg 0.55.0, x11 2.21.0, x11-dl 2.21.0, xdg-home 1.3.0, zbus 3.15.2, zbus_macros 3.15.2, zbus_names 2.6.1, zmij 1.0.23, zvariant 3.15.2, zvariant_derive 3.15.2, zvariant_utils 1.0.1


### MIT OR Apache-2.0 (262 crates)

aes 0.8.4, android_system_properties 0.1.6, anyhow 1.0.104, async-broadcast 0.5.1, async-recursion 1.1.1, async-trait 0.1.92, base64 0.21.7, base64 0.22.1, bitflags 2.13.1, block-buffer 0.10.4, block-padding 0.3.3, bumpalo 3.20.3, camino 1.2.5, cargo-platform 0.1.9, cbc 0.1.2, cc 1.4.4, cfg-expr 0.15.8, cfg-if 1.0.4, chrono 0.4.45, cipher 0.4.4, cookie 0.18.2, core-foundation 0.10.1, core-foundation 0.9.4, core-foundation-sys 0.8.7, core-graphics 0.25.0, core-graphics-types 0.2.0, cpufeatures 0.2.17, crc32fast 1.5.1, crossbeam-channel 0.5.16, crossbeam-utils 0.8.22, crypto-common 0.1.7, defmt 1.1.1, defmt-macros 1.1.1, defmt-parser 1.0.0, deranged 0.5.8, digest 0.10.7, dirs 6.0.0, dirs-sys 0.5.0, displaydoc 0.2.7, dtoa 1.0.11, dyn-clone 1.0.20, embed_plist 1.2.2, enumflags2 0.7.12, enumflags2_derive 0.7.12, erased-serde 0.4.10, errno 0.3.14, fdeflate 0.3.7, field-offset 0.3.6, find-msvc-tools 0.1.11, flate2 1.1.9, form_urlencoded 1.2.2, futures-channel 0.3.34, futures-core 0.3.34, futures-executor 0.3.34, futures-io 0.3.34, futures-macro 0.3.34, futures-sink 0.3.34, futures-task 0.3.34, futures-util 0.3.34, getrandom 0.2.17, getrandom 0.3.4, getrandom 0.4.3, glob 0.3.4, hashbrown 0.12.3, hashbrown 0.14.5, hashbrown 0.17.1, heck 0.4.1, heck 0.5.0, hermit-abi 0.3.9, hermit-abi 0.5.2, hex 0.4.3, hkdf 0.12.4, hmac 0.12.1, html5ever 0.38.0, http 1.5.0, httparse 1.10.1, iana-time-zone 0.1.65, iana-time-zone-haiku 0.1.2, idna 1.1.0, inout 0.1.4, ipnet 2.12.1, itoa 1.0.18, jni-sys 0.3.1, jni-sys 0.4.1, jni-sys-macros 0.4.1, js-sys 0.3.104, jsonptr 0.6.3, keyboard-types 0.7.0, keyring 2.3.3, lazy_static 1.5.0, libc 0.2.189, lock_api 0.4.14, log 0.4.34, markup5ever 0.38.0, mime 0.3.17, ndk 0.9.0, ndk-sys 0.6.0+11769913, num 0.4.3, num-bigint 0.4.8, num-complex 0.4.6, num-conv 0.2.2, num-integer 0.1.47, num-iter 0.1.46, num-rational 0.4.2, num-traits 0.2.19, once_cell 1.21.4, ordered-stream 0.2.0, parking_lot 0.12.5, parking_lot_core 0.9.12, percent-encoding 2.3.2, piper 0.2.5, pkg-config 0.3.34, png 0.17.16, png 0.18.1, powerfmt 0.2.0, ppv-lite86 0.2.21, proc-macro-crate 1.3.1, proc-macro-crate 2.0.2, proc-macro-crate 3.5.0, proc-macro-error 1.0.4, proc-macro-error-attr 1.0.4, proc-macro2 1.0.107, quote 1.0.47, rand 0.8.8, rand_chacha 0.3.1, rand_core 0.6.4, ref-cast 1.0.27, ref-cast-impl 1.0.27, regex 1.13.1, regex-automata 0.4.18, regex-syntax 0.8.11, reqwest 0.13.4, rustc_version 0.4.1, rustversion 1.0.23, scopeguard 1.2.0, secret-service 3.1.0, security-framework 2.11.1, security-framework-sys 2.17.0, semver 1.0.28, serde 1.0.229, serde-untagged 0.1.9, serde_core 1.0.229, serde_derive 1.0.229, serde_derive_internals 0.29.1, serde_json 1.0.151, serde_repr 0.1.21, serde_spanned 0.6.9, serde_spanned 1.1.1, serde_with 3.22.0, serde_with_macros 3.22.0, serialize-to-javascript 0.1.2, serialize-to-javascript-impl 0.1.2, servo_arc 0.4.3, sha1 0.10.7, sha2 0.10.9, shlex 2.0.1, signal-hook-registry 1.4.8, smallvec 1.15.2, socket2 0.4.10, socket2 0.6.5, softbuffer 0.4.8, stable_deref_trait 1.2.1, static_assertions 1.1.0, string_cache 0.9.0, string_cache_codegen 0.6.1, swift-rs 1.0.8, syn 1.0.109, syn 2.0.119, syn 3.0.3, syn 3.0.4, system-deps 6.2.2, tao-macros 0.1.4, tempfile 3.27.0, tendril 0.5.1, thiserror 1.0.69, thiserror 2.0.20, thiserror-impl 1.0.69, thiserror-impl 2.0.20, time 0.3.55, time-core 0.1.9, time-macros 0.2.32, toml 0.8.2, toml 0.9.12+spec-1.1.0, toml 1.1.4+spec-1.1.0, toml_datetime 0.6.11, toml_datetime 0.6.3, toml_datetime 0.7.5+spec-1.1.0, toml_datetime 1.1.1+spec-1.1.0, toml_edit 0.19.15, toml_edit 0.20.2, toml_edit 0.25.13+spec-1.1.0, toml_parser 1.1.3+spec-1.1.0, toml_writer 1.1.2+spec-1.1.0, tray-icon 0.24.2, typeid 1.0.3, typenum 1.20.1, unicode-segmentation 1.13.3, url 2.5.8, wasm-bindgen 0.2.127, wasm-bindgen-futures 0.4.77, wasm-bindgen-macro 0.2.127, wasm-bindgen-macro-support 0.2.127, wasm-bindgen-shared 0.2.127, wasm-streams 0.5.0, web-sys 0.3.104, web_atoms 0.2.6, windows 0.61.3, windows-collections 0.2.0, windows-core 0.61.2, windows-core 0.62.2, windows-future 0.2.1, windows-implement 0.60.2, windows-interface 0.59.3, windows-link 0.1.3, windows-link 0.2.1, windows-numerics 0.2.0, windows-result 0.3.4, windows-result 0.4.1, windows-strings 0.4.2, windows-strings 0.5.1, windows-sys 0.45.0, windows-sys 0.48.0, windows-sys 0.52.0, windows-sys 0.59.0, windows-sys 0.60.2, windows-sys 0.61.2, windows-targets 0.42.2, windows-targets 0.48.5, windows-targets 0.52.6, windows-targets 0.53.5, windows-threading 0.1.0, windows-version 0.1.7, windows_aarch64_gnullvm 0.42.2, windows_aarch64_gnullvm 0.48.5, windows_aarch64_gnullvm 0.52.6, windows_aarch64_gnullvm 0.53.1, windows_aarch64_msvc 0.42.2, windows_aarch64_msvc 0.48.5, windows_aarch64_msvc 0.52.6, windows_aarch64_msvc 0.53.1, windows_i686_gnu 0.42.2, windows_i686_gnu 0.48.5, windows_i686_gnu 0.52.6, windows_i686_gnu 0.53.1, windows_i686_gnullvm 0.52.6, windows_i686_gnullvm 0.53.1, windows_i686_msvc 0.42.2, windows_i686_msvc 0.48.5, windows_i686_msvc 0.52.6, windows_i686_msvc 0.53.1, windows_x86_64_gnu 0.42.2, windows_x86_64_gnu 0.48.5, windows_x86_64_gnu 0.52.6, windows_x86_64_gnu 0.53.1, windows_x86_64_gnullvm 0.42.2, windows_x86_64_gnullvm 0.48.5, windows_x86_64_gnullvm 0.52.6, windows_x86_64_gnullvm 0.53.1, windows_x86_64_msvc 0.42.2, windows_x86_64_msvc 0.48.5, windows_x86_64_msvc 0.52.6, windows_x86_64_msvc 0.53.1


### MIT OR Apache-2.0 OR LGPL-2.1-or-later (2 crates)

r-efi 5.3.0, r-efi 6.0.0


### MIT OR Apache-2.0 OR Zlib (2 crates)

raw-window-handle 0.6.2, tinyvec_macros 0.1.1


### MIT OR Zlib OR Apache-2.0 (1 crate)

miniz_oxide 0.8.9


### MIT/Apache-2.0 (19 crates)

bitflags 1.3.2, bs58 0.5.1, derivative 2.2.0, foreign-types 0.5.0, foreign-types-macros 0.2.4, foreign-types-shared 0.3.1, ident_case 1.0.1, jni 0.21.1, json-patch 3.0.1, siphasher 1.0.3, unic-char-property 0.9.0, unic-char-range 0.9.0, unic-common 0.9.0, unic-ucd-ident 0.9.0, unic-ucd-version 0.9.0, version_check 0.9.5, winapi 0.3.9, winapi-i686-pc-windows-gnu 0.4.0, winapi-x86_64-pc-windows-gnu 0.4.0


### MPL-2.0 (5 crates)

cssparser 0.36.0, cssparser-macros 0.6.1, dtoa-short 0.3.5, option-ext 0.2.0, selectors 0.36.1


### Unicode-3.0 (18 crates)

icu_collections 2.3.0, icu_locale_core 2.3.0, icu_normalizer 2.3.0, icu_normalizer_data 2.3.0, icu_properties 2.3.0, icu_properties_data 2.3.0, icu_provider 2.3.1, litemap 0.8.3, potential_utf 0.1.6, tinystr 0.8.4, writeable 0.6.4, yoke 0.8.3, yoke-derive 0.8.2, zerofrom 0.1.8, zerofrom-derive 0.1.7, zerotrie 0.2.5, zerovec 0.11.8, zerovec-derive 0.11.6


### Unlicense OR MIT (9 crates)

aho-corasick 1.1.5, byteorder 1.5.0, jiff 0.2.35, jiff-core 0.1.0, jiff-static 0.2.35, jiff-tzdb 0.1.8, jiff-tzdb-platform 0.1.3, memchr 2.8.3, winapi-util 0.1.11


### Unlicense/MIT (2 crates)

same-file 1.0.6, walkdir 2.5.0


### Zlib (1 crate)

foldhash 0.2.0


### Zlib OR Apache-2.0 OR MIT (17 crates)

bytemuck 1.25.2, dispatch2 0.3.1, objc2-app-kit 0.3.2, objc2-cloud-kit 0.3.2, objc2-core-data 0.3.2, objc2-core-foundation 0.3.2, objc2-core-graphics 0.3.2, objc2-core-image 0.3.2, objc2-core-location 0.3.2, objc2-core-text 0.3.2, objc2-exception-helper 0.1.1, objc2-io-surface 0.3.2, objc2-quartz-core 0.3.2, objc2-ui-kit 0.3.2, objc2-user-notifications 0.3.2, objc2-web-kit 0.3.2, tinyvec 1.12.0


## Full third-party notice / license texts

This document records license identifiers and attribution, not the full text of every third-party license. Several of the licenses above (e.g. Apache-2.0, BSD-3-Clause) require the license text and/or copyright notice to be reproduced when redistributing the software. For a public release, the full license text of each distinct license family listed above should be bundled alongside the installer (e.g. in a `licenses/` folder shipped with the Windows installer) or linked from the application's About dialog. That bundling step has not yet been implemented and is tracked as follow-up work, not represented here as complete.


## Verification status

All license identifiers above were retrieved from each package's own published metadata at the exact resolved version shipped. No license was assumed, guessed, or copied from a different version of a package. If a future dependency change is not reflected here, this document is stale and should be regenerated from the then-current lockfiles before release.
