This guide covers:

✅ Installing CAC reader support on Linux
✅ Verifying reader detection
✅ Testing CoolKey/OpenSC functionality
✅ Installing DoD PKI certificates
✅ Installing the correct Oracle VirtualBox Extension Pack
✅ Configuring USB pass-through
✅ Connecting the CAC reader to the Windows VM
✅ Testing CAC authentication

Step 1: Install Smart Card Middleware on Pop!_OS

Install the required packages:

sudo apt update

sudo apt install opensc pcscd pcsc-tools

These packages provide:

Package	Purpose
OpenSC	Smart card middleware
pcscd	Smart card daemon
pcsc-tools	Reader testing utilities

Step 2: Enable Smart Card Services

Start the smart card daemon:

sudo systemctl enable pcscd --now

Verify:
sudo systemctl status pcscd

Expected:
active (running)

Step 3: Verify Linux Detects the CAC Reader

Insert the reader and CAC card.
Run:
pcsc_scan

Expected output:
Reader 0:
Card inserted
ATR:

If the reader and card appear:
✅ Hardware communication is working

Exit:
Ctrl + C

Step 4: Test Smart Card Middleware

Verify OpenSC can see the card:
opensc-tool -l

Expected:
Readers known about:
0: Identiv SCR3310

Next:
pkcs15-tool -D

Expected:
X.509 certificates
Authentication certificate
Email certificate

This confirms OpenSC can communicate with the CAC.

Step 5: Install CoolKey (Optional Legacy Validation)

Some government environments still reference CoolKey.

Install:

sudo apt install coolkey

Test:
modutil -dbdir sql:$HOME/.pki/nssdb -list
Verify the middleware loads correctly.

While OpenSC is generally preferred today, validating CoolKey compatibility can help troubleshoot legacy environments.

Step 6: Install DoD PKI Certificates

Download the DoD PKI bundle.

Convert:

openssl pkcs7 -print_certs -inform DER \
-in certificates.der.p7b \
-out dod.pem

Split:
mkdir dod-certs

csplit -z dod.pem \
'/-----BEGIN CERTIFICATE-----/' \
'{*}' \
-f dod-certs/cert- \
-b '%03d.crt'

Install:

sudo mkdir -p /usr/local/share/ca-certificates/dod

sudo cp dod-certs/*.crt \
/usr/local/share/ca-certificates/dod/

sudo update-ca-certificates

Expected:

XX added, 0 removed

Step 7: Install the Correct VirtualBox Extension Pack

This is where many setups fail.
The Extension Pack version MUST match the VirtualBox version exactly.

Check VirtualBox version:

VBoxManage --version

Example:

7.1.12r169651

Download the matching Extension Pack from:

Oracle Corporation

Specifically:

VirtualBox 7.1.12
Extension Pack 7.1.12

Version mismatches will cause:

USB failures
Missing USB 2.0/3.0 support
Reader pass-through issues

Install:

sudo VBoxManage extpack install \
Oracle_VM_VirtualBox_Extension_Pack.vbox-extpack

Verify:

VBoxManage list extpacks

Expected:

Oracle VM VirtualBox Extension Pack
Step 8: Add Your User to the VirtualBox USB Group

Without this step, VirtualBox cannot access USB devices.

Add user:

sudo usermod -aG vboxusers $USER

Log out completely.

Log back in.

Verify:

groups

Expected:
vboxusers

appears in the output.

Step 9: Configure USB Support in VirtualBox

Open VirtualBox.
Select the VM.

Navigate:

Settings
 → USB

Enable:

✅ USB Controller

Choose:
USB 3.0 (xHCI)

or

USB 2.0 (EHCI)
depending on the reader.

Step 10: Create a USB Filter

With the reader plugged in:

Settings
 → USB
 → Add USB Filter

Select:

Identiv
SCR3310
CAC Reader

or your reader model.

This allows VirtualBox to automatically capture the device.

Step 11: Start the Windows VM in Oracle VirtualBox

Launch Windows.

Insert CAC.

Navigate:

Devices
 → USB

Select your reader.

If successful:

The reader disappears from Linux and appears in Windows.

This is expected.

Step 12: Install Windows Smart Card Drivers

Inside Windows:

Install:

ActivClient (if required) and InstallRoot.exe
Native Windows Smart Card support

Verify:

Device Manager
 → Smart Card Readers

No warning icons should appear.

Step 13: Verify the CAC in Windows

Open:

certmgr.msc

You should see:

Authentication certificate
Email certificate

associated with your CAC.

Step 14: Test Authentication

Test:

OWA
milConnect
portal.apps.mil
Government VPN solutions

Expected:

✅ Certificate selection prompt
✅ PIN prompt
✅ Successful login

Common Problems
USB Device Busy

Linux still owns the reader.

Stop pcscd temporarily:

sudo systemctl stop pcscd

Start VM.

Connect reader.

Restart after testing:

sudo systemctl start pcscd
VirtualBox Cannot See Reader

Verify:

groups

Contains:

vboxusers
Reader Missing from USB Menu

Verify Extension Pack version matches VirtualBox exactly.

This is the most common failure point.

CAC Visible on Host but Not Guest

Use:

Devices
 → USB

and manually attach the reader.
