# Omega Omarchy native technical-alpha bundle

Run `./omega-omarchy` from this directory. No installation, repository
checkout, compiler, network connection, or system Python is required. This
portable directory writes saves and configuration only under the normal user
data locations documented below; removing the bundle does not remove them.

Useful commands:

```text
./omega-omarchy
./omega-omarchy version
./omega-omarchy dump-identity --seed omega-fixture-1
```

Player saves use `$XDG_DATA_HOME/omega-omarchy/save.json`, falling back to
`~/.local/share/omega-omarchy/save.json`. Remove or back up that directory
separately if desired. The bundle has no uninstaller and never deletes player
data automatically.

This is a technical-alpha artifact whose qualified product boundary is
Chapter 1. Chapters 2–6 remain development scaffolding, and the HTML build is a
preview rather than a feature-equivalent port.

Omega Omarchy is an unofficial parody/fan project. It is not affiliated with,
authorized by, sponsored by, or endorsed by Omarchy or its maintainers. The
code license does not grant rights in third-party names, marks, logos, or any
real person's name, likeness, voice, or persona.

Controls and accessibility guidance are included in `docs/`. Build provenance,
dependency versions, and the source commit are in `BUILD-INFO.json` and
`DEPENDENCIES.json`. License scopes and third-party notices are included beside
this file.

Support and source:
https://github.com/Omega-Omarchy/omega-omarchy
