# Omarchy installer study (version-bound)

Study date: 2026-08-28  
Observation class: **VM-observed** on a disposable QEMU TCG guest, plus the
earlier **source-observed** beat sheet.

## Identities

| Item | Value | How known |
|---|---|---|
| Omarchy ISO file | `omarchy-4.0.1.iso` from `https://iso.omarchy.org/omarchy-4.0.1.iso` | official current as of 2026-08-28; SHA-256 file matched |
| ISO SHA-256 | `69cbb4e10d98ad831c3c9f245b5757a9d1fedfd0c9592780e977d6f950dea8c3` | `sha256sum -c` against the published `.sha256` |
| ISO size | 6 227 752 960 bytes | `stat` |
| ISO last-modified | 2026-08-25 11:22:31 GMT | HTTP |
| Live kernel string at login | `Omarchy 7.1.8-arch1-Watanare-T2-3-t2` | VM-observed archiso autologin flash |
| Omarchy git | `83881e979b35468c3e7d60b171e319ede61a88fd` (2026-08-27) | source checkout |
| omarchy-iso git | `268bac16d351a21d867e37565738f458b11cb06c` (2026-08-23) | source checkout |
| QEMU | 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18) | host |
| Firmware | OVMF_CODE_4M.fd / private copy of OVMF_VARS_4M.fd | SHA-256 in private record |
| Machine | q35, 4 vCPU, 8 GiB RAM, 48 GiB virtio QCOW2, virtio-net user | |
| Acceleration | `-accel tcg,thread=multi` — **no KVM** | |
| Timings | software-emulated only; not representative of real Omarchy hardware | |

Current official ISO remains 4.0.1; no silent substitution. Raw captures, ISO,
and disks live under the gitignored `.local/omarchy-vm/` workspace.

## VM-observed sequence

1. **UEFI** boots `UEFI QEMU DVD-ROM`. Brief archiso autologin line, then the
   greeter.
2. **Greeter (centered):** enormous lime block `OMARCHY` wordmark on a
   near-black Tokyo Night canvas; a cyan bar drifts through the letters
   (colorshift); tagline `Beautiful, Modern & Opinionated Linux by DHH`; dim
   hint `Press Return to Start Install`. Huge negative space. No other chrome.
3. **After Return:** wordmark **pins to the top**. Copy `Let's setup your
   machine...` then `Press Ctrl+C to prepare this machine for another owner.`
4. **Keyboard:** `Select keyboard layout`. English (US) selected first, then
   UK / Dvorak / Colemak, then alphabetical. Footer
   `←↓↑→ navigate • enter submit`.
5. **Account:** header becomes `Let's setup your user account...`. Purple
   prompt labels, gray placeholders:
   - `Username>` `Alphanumeric without spaces (like dhh)`
   - `Password>` `Used for user + root, and disk encryption when enabled`
     (masked)
   - `Full name>` / `Email address>` `Used for git authentication (hit return
     to skip)`
   - `Hostname>` `Letters, digits, and dashes (or return for 'omarchy')`
   - `Timezone` searchable list (geo-guessed selection when tzupdate works)
6. **Confirm table:** Field/Value including `[Skipped]` and password
   asterisks. `Does this look right?` Lime **Yes** button vs `No, change it`.
   Shortcuts `y` / `n`.
7. **Disk:** `Let's select where to install Omarchy...` then
   `Select install disk` (`/dev/vda (48G)` here). Empty disk skipped the
   free-space/cfdisk mode picker (**correction vs source-only sheet**).
8. **Overwrite:** `Everything will be overwritten. There is no recovery
   possible.` `Press Ctrl+C for unencrypted install.` Lime
   `Yes, install` vs `No, change it`. **The game never performs this step.**
9. **Progress (user-visible):** centered wordmark again, subtitle
   `Installing Omarchy`, a **dotted bar** filling left-to-right in lavender,
   rotating lime `Tip:` lines (Super+Space, Super key, Pinta/Kdenlive/LibreOffice,
   LocalSend, Update menu, …). Internal dashboard phase names are **not**
   shown. TCG fill is slow; timings are emulated.
10. **Reboot Now (VM-observed):** centered wordmark, copy
    `Installed Omarchy in 26m 11s` (**TCG wall time, not hardware**), and a
    single lime **Reboot Now** button with no visible negative action. Same
    composition as the greeter/progress screens. Game completion remains
    **Play Now**.

## Mapping

| Observed Omarchy | Source sheet | Omega Omarchy | Disposition |
|---|---|---|---|
| Centered greeter, colorshift, Return to start | matched | Centered wordmark, same hint, cyan pulse (off if reduced-motion) | **corrected from VM** |
| Logo pins top for setup | not emphasized | Setup pages pin the wordmark at the top | **corrected from VM** |
| Ctrl+C other-owner / unencrypted | source-known | Not offered (non-destructive game) | **justified divergence** |
| gum lists + purple prompts | source-known | `>` selected row, Left/Right change, Z/Return next | **parody** |
| Confirm table + Yes / No, change it | source-known | Field/Value table; Yes vs No, change it (returns to character) | **corrected from VM** |
| Disk wipe confirm | source-known | Omitted | **required non-destructive** |
| Named phase list | source-internal | Was wrongly shown; now dotted bar + rotating tips | **corrected from VM** |
| Reboot Now lime button | source-known | **Play Now** lime button | **intentional parody** |

Artificial delay remains skippable. Generation is real and does not wait on a
fake reboot.
