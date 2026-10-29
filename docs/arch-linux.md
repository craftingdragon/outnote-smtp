# Arch Linux packages and user service

This is an alternative to the virtual environment install in [the usage tutorial](usage.md). It installs three native Arch packages: `python-ms-entrance`, `python-outnote`, and `outnote-smtp`. The SMTP package depends on `python-outnote`; OutNote in turn depends on Entrance. The bridge uses Arch's `python-aiosmtpd` and `radicale` packages. These PKGBUILDs build from source and do not run `pip install` into the system Python environment.

## Build and install

Run these commands from this repository on Arch Linux. `makepkg -si` installs each local package and its repository dependencies. Do not run `makepkg` as root.

```bash
sudo pacman -Syu --needed base-devel python-build python-installer python-uv-build python-hatchling

cd packaging/arch/python-ms-entrance
makepkg -si

cd ../python-outnote
makepkg -si

cd ../outnote-smtp
cd ../../..
python -m build --sdist --no-isolation
cp dist/outnote_smtp-0.2.1.tar.gz packaging/arch/outnote-smtp/
cd packaging/arch/outnote-smtp
makepkg -si
```

The Entrance and OutNote PKGBUILDs use pinned PyPI source releases and SHA-256 checksums. Their upstream source pins an older `uv_build` range; the PKGBUILDs use Arch's installed backend and skip only that build dependency check. The SMTP PKGBUILD uses the local source archive generated from this checkout. Its checksum is marked `SKIP` until this project has a published release archive; verify the checkout before building and replace `SKIP` with a release checksum before distributing the PKGBUILD.

To use a newer development version, update `pkgver` in the matching PKGBUILD and its source URL/checksum, then rebuild in dependency order. For unreleased SMTP changes, build a fresh source archive from the checkout and update the SMTP PKGBUILD's `pkgver` to match the project version.

## Sign in and start the user service

Sign in as the same desktop user who will run the service:

```bash
outnote-smtp login
systemctl --user daemon-reload
systemctl --user enable --now outnote-smtp.service
systemctl --user status outnote-smtp.service
```

The service runs `outnote-smtp serve --verbose`. It reads the saved token from your user state directory and listens on `127.0.0.1:1025` for SMTP and `127.0.0.1:5232` for CardDAV. View its startup and mail-submission logs with:

```bash
journalctl --user -u outnote-smtp.service -f
```

To run without CardDAV, add a user-level service override with `systemctl --user edit outnote-smtp.service`:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/outnote-smtp serve --verbose --no-carddav
```

Then run `systemctl --user daemon-reload` and `systemctl --user restart outnote-smtp.service`. The empty `ExecStart=` line clears the packaged command before setting the replacement.

To stop automatic startup, run `systemctl --user disable --now outnote-smtp.service`. The package installation does not enable the service automatically.
