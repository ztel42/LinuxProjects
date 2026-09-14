# DoD CAC + Certificates in Brave on Linux

Manual steps that got a **DoD Common Access Card (CAC)** working with **Brave** on **Pop!_OS / Ubuntu** (Flatpak Brave). Tested on Pop!_OS 24.04 with Flatpak Brave and an Alcor Micro USB reader.

This is a workstation guide, not official DoD policy. Use only official DoD PKI material. Never paste or store your CAC PIN in chat, scripts, or password managers that sync insecurely — enter the PIN only in the browser/OS prompt when asked.

---

## What you need

- Linux desktop (Pop!_OS / Ubuntu noble or similar)
- USB CAC reader + DoD CAC
- Brave (Flatpak `com.brave.Browser` **or** native `.deb`)
- Ability to use `sudo` / PolicyKit (`pkexec`)

### Layers that must all work

1. **Reader** — kernel + CCID driver see the USB device  
2. **PC/SC** — `pcscd` exposes the reader  
3. **OpenSC** — PKCS#11 middleware reads PIV slots on the CAC  
4. **Trust** — DoD root/intermediate CAs trusted by the system and/or browser  
5. **Browser** — NSS database loads the OpenSC PKCS#11 module (Flatpak needs extra sandbox work)

---

## 1. Install packages

```bash
sudo apt update
sudo apt install -y \
  pcscd pcsc-tools libccid \
  opensc opensc-pkcs11 \
  libnss3-tools \
  p11-kit p11-kit-modules
```

Optional but common: `coolkey` (older middleware; OpenSC is preferred for modern PIV CACs).

Enable and start PC/SC:

```bash
sudo systemctl enable --now pcscd
sudo systemctl status pcscd --no-pager
```

### Quick hardware check

Insert the CAC, then:

```bash
opensc-tool --list-readers
pkcs11-tool --module /usr/lib/x86_64-linux-gnu/opensc-pkcs11.so -O
```

You should see your reader and PIV certificate objects (PIV Authentication, Digital Signature, Key Management, Card Authentication). Public objects usually do **not** require a PIN.

---

## 2. Download official DoD certificates

Get the current **unclassified DoD PKCS#7 certificate bundle** only from DoD Cyber Exchange / `dl.dod.cyber.mil` (not random mirrors).

Example URL (version may change):

```text
https://dl.dod.cyber.mil/wp-content/uploads/pki-pke/zip/unclass-certificates_pkcs7_DoD.zip
```

```bash
mkdir -p ~/cac-setup && cd ~/cac-setup
curl -fL -o unclass-certificates_pkcs7_DoD.zip \
  'https://dl.dod.cyber.mil/wp-content/uploads/pki-pke/zip/unclass-certificates_pkcs7_DoD.zip'
unzip -o unclass-certificates_pkcs7_DoD.zip -d Certificates_PKCS7_DoD
```

Split PEMs if needed (bundle layout varies by version):

```bash
mkdir -p ~/cac-setup/pem-split
# Adjust the .p7b filename to match what you extracted
openssl pkcs7 -print_certs -in Certificates_PKCS7_DoD/*.p7b \
  | awk 'split_after==1{n++;split_after=0} /-----END CERTIFICATE-----/ {split_after=1} {print > ("pem-split/cert" n ".pem")}'
```

Or use any `DoD_PKE_CA_chain.pem` / individual CA PEMs shipped in the zip.

---

## 3. Install DoD CAs into the system trust store

```bash
sudo mkdir -p /usr/local/share/ca-certificates/DoD
# Copy each CA as a .crt (OpenSSL PEM content is fine)
sudo cp ~/cac-setup/pem-split/*.pem /usr/local/share/ca-certificates/DoD/
# Rename to .crt if needed
sudo bash -c 'cd /usr/local/share/ca-certificates/DoD && for f in *.pem; do mv "$f" "${f%.pem}.crt"; done'
sudo update-ca-certificates
```

Chromium-family browsers often also need the CAs in the **NSS** DB (next section).

---

## 4. Register OpenSC in the host NSS database

Chromium / Brave use NSS at `~/.pki/nssdb`.

```bash
mkdir -p ~/.pki/nssdb
# Only if the DB does not exist yet:
# certutil -N -d sql:$HOME/.pki/nssdb --empty-password

modutil -dbdir sql:$HOME/.pki/nssdb -list
```

If **OpenSC** is not listed:

```bash
modutil -dbdir sql:$HOME/.pki/nssdb -force \
  -add "OpenSC" \
  -libfile /usr/lib/x86_64-linux-gnu/pkcs11/onepin-opensc-pkcs11.so
```

Prefer **`onepin-opensc-pkcs11.so`** (single PIN prompt) over plain `opensc-pkcs11.so` when both exist.

Import DoD CAs into NSS (trust for SSL websites):

```bash
for f in ~/cac-setup/pem-split/*.pem; do
  nick=$(basename "$f" .pem)
  certutil -A -d sql:$HOME/.pki/nssdb -n "DoD-$nick" -t "CT,C,C" -i "$f" || true
done
certutil -L -d sql:$HOME/.pki/nssdb | head
```

---

## 5. Flatpak Brave — required extra steps

Flatpak **cannot mount host `/usr`**. If NSS points at `/usr/lib/.../opensc-pkcs11.so`, Brave inside the sandbox will **not** load it → no CAC certs, no PIN prompt, and vague errors like *“Unexpected error occurred validating your certificate”*.

### 5a. Bundle OpenSC where Flatpak can see it

```bash
mkdir -p ~/cac-setup/pkcs11-libs
cp -a /usr/lib/x86_64-linux-gnu/pkcs11/onepin-opensc-pkcs11.so ~/cac-setup/pkcs11-libs/
cp -a /usr/lib/x86_64-linux-gnu/pkcs11/opensc-pkcs11.so ~/cac-setup/pkcs11-libs/
# Copy shared libs OpenSC needs (names/versions may vary slightly)
cp -a /usr/lib/x86_64-linux-gnu/libopensc.so* ~/cac-setup/pkcs11-libs/
cp -a /usr/lib/x86_64-linux-gnu/libeac.so* ~/cac-setup/pkcs11-libs/ 2>/dev/null || true
cp -a /usr/lib/x86_64-linux-gnu/libpcsclite.so* ~/cac-setup/pkcs11-libs/
```

Set RPATH so the module finds sibling libs (requires `patchelf` if not already set):

```bash
sudo apt install -y patchelf
patchelf --set-rpath '$ORIGIN' ~/cac-setup/pkcs11-libs/onepin-opensc-pkcs11.so
patchelf --set-rpath '$ORIGIN' ~/cac-setup/pkcs11-libs/opensc-pkcs11.so
```

### 5b. Flatpak overrides

```bash
flatpak override --user \
  --filesystem="$HOME/cac-setup/pkcs11-libs:ro" \
  --filesystem=xdg-run/p11-kit/pkcs11 \
  --env=LD_LIBRARY_PATH="$HOME/cac-setup/pkcs11-libs" \
  com.brave.Browser

flatpak override --user --show com.brave.Browser
```

Brave’s Flatpak manifest already includes `--socket=pcsc` and `persistent=.pki` on current Flathub builds.

### 5c. Point Brave’s NSS DB at the bundled module

Fully quit Brave first. Brave Flatpak NSS DB:

```text
~/.var/app/com.brave.Browser/.pki/nssdb
```

```bash
# Backup
cp -a ~/.var/app/com.brave.Browser/.pki/nssdb/pkcs11.txt \
      ~/.var/app/com.brave.Browser/.pki/nssdb/pkcs11.txt.bak

modutil -dbdir sql:$HOME/.var/app/com.brave.Browser/.pki/nssdb -list

# Remove old broken OpenSC entry if it points at /usr/...
modutil -dbdir sql:$HOME/.var/app/com.brave.Browser/.pki/nssdb -force \
  -delete "OpenSC" 2>/dev/null || true

modutil -dbdir sql:$HOME/.var/app/com.brave.Browser/.pki/nssdb -force \
  -add "OpenSC" \
  -libfile "$HOME/cac-setup/pkcs11-libs/onepin-opensc-pkcs11.so"
```

Import DoD CAs into the **Brave** NSS DB the same way as the host DB (`certutil -A ... -t "CT,C,C"`).

### 5d. Optional: user `p11-kit-server` (helps some Flatpak setups)

Distros may not ship user units. Example that stays running (note `-f`):

`~/.config/systemd/user/p11-kit-server.socket`

```ini
[Unit]
Description=p11-kit server socket

[Socket]
ListenStream=%t/p11-kit/pkcs11
SocketMode=0600

[Install]
WantedBy=sockets.target
```

`~/.config/systemd/user/p11-kit-server.service`

```ini
[Unit]
Description=p11-kit server
Requires=p11-kit-server.socket

[Service]
Type=simple
ExecStart=/usr/libexec/p11-kit/p11-kit-server -f -n %t/p11-kit/pkcs11 pkcs11:
Restart=on-failure
RestartSec=1
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now p11-kit-server.socket
systemctl --user status p11-kit-server.service --no-pager
```

Without `-f`, the server can exit immediately and hit start-limit.

---

## 6. Verify inside Flatpak (optional)

```bash
flatpak run --command=sh com.brave.Browser -c \
  'LD_LIBRARY_PATH=$HOME/cac-setup/pkcs11-libs \
   $HOME/cac-setup/pkcs11-libs/pkcs11-tool \
   --module $HOME/cac-setup/pkcs11-libs/onepin-opensc-pkcs11.so -O' 
```

(If you copied `pkcs11-tool` into `pkcs11-libs`, or call host `pkcs11-tool` with the bundled module path from outside Flatpak.)

Host-side check is enough for most people:

```bash
pkcs11-tool --module "$HOME/cac-setup/pkcs11-libs/onepin-opensc-pkcs11.so" -O
```

---

## 7. Use it in Brave

1. Insert CAC; confirm reader activity.  
2. Fully quit and relaunch Brave.  
3. Open `brave://settings/certificates` (or `chrome://settings/certificates`):  
   - **Authorities** — DoD CAs present  
   - **Your certificates** — CAC / OpenSC token certs  
4. Visit a CAC-enabled site (e.g. DoD portals / `https://cyber.mil`).  
5. When prompted, enter your **CAC PIN only in that dialog**. Do not save it.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| No PIN prompt; no certs in Brave | Flatpak can’t load `/usr` PKCS#11 | Bundle libs under `~/cac-setup/pkcs11-libs`, override Flatpak, repoint NSS |
| “Unexpected error occurred validating your certificate” | Module not loading and/or missing DoD intermediates | Fix PKCS#11 path; re-import full DoD CA set into Brave NSS |
| `opensc-tool` sees nothing | Reader/card/`pcscd` | Reseat card; `sudo systemctl restart pcscd`; try another USB port |
| Works on host tools, not in Brave | Wrong NSS DB edited | Edit `~/.var/app/com.brave.Browser/.pki/nssdb` for Flatpak |
| Broke after Brave/OpenSC update | Bundled `.so` stale or override lost | Re-copy libs; re-check `flatpak override --show` |
| Still flaky in Flatpak | Sandbox friction | Install **native Brave `.deb`** and use host `~/.pki/nssdb` + `/usr/.../onepin-opensc-pkcs11.so` |

Check overrides and services:

```bash
flatpak override --user --show com.brave.Browser
systemctl is-active pcscd
systemctl --user status p11-kit-server.service --no-pager
opensc-tool --list-readers
```

---

## 9. Native Brave (optional, often more reliable for CAC)

If Flatpak remains painful:

1. Install Brave’s official `.deb` from Brave’s Linux instructions.  
2. Register OpenSC against `~/.pki/nssdb` pointing at `/usr/lib/x86_64-linux-gnu/pkcs11/onepin-opensc-pkcs11.so`.  
3. Keep DoD CAs in system trust + that NSS DB.  
4. You can keep or remove the Flatpak app afterward.

---

## 10. Security notes

- Enter the CAC PIN only when the browser/OS prompts you.  
- Do not put the PIN in shell history, scripts, or chat.  
- Prefer official DoD Cyber Exchange bundles for CA trust material.  
- Flatpak overrides that expose PKCS#11 / PC/SC increase what the browser can reach — expected for smart-card login, but don’t widen overrides beyond what you need.  
- On shared or managed machines, follow your organization’s IAM / STIGs instead of this guide when they conflict.

---

## Paths used on this Pop!_OS setup

| Item | Path |
|------|------|
| Work directory | `~/cac-setup/` |
| Bundled PKCS#11 (Flatpak) | `~/cac-setup/pkcs11-libs/onepin-opensc-pkcs11.so` |
| Host NSS DB | `~/.pki/nssdb` |
| Flatpak Brave NSS DB | `~/.var/app/com.brave.Browser/.pki/nssdb` |
| Host OpenSC module | `/usr/lib/x86_64-linux-gnu/pkcs11/onepin-opensc-pkcs11.so` |
| DoD CA zip (local copy) | `~/cac-setup/unclass-certificates_pkcs7_DoD.zip` |

---

*Documented from a working Flatpak Brave + DoD CAC setup on Pop!_OS 24.04 (September 2026).*
