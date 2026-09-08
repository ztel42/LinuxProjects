Complete Guide: Setting Up DoD CAC Authentication on Pop!_OS Linux with Firefox

Running CAC authentication on Linux can feel intimidating the first time, especially if you are coming from a Windows environment where InstallRoot and middleware installers handle everything automatically. After working through the process end-to-end on Pop!_OS with Firefox, here is a streamlined process that takes you from zero to a working CAC-enabled browser.

This guide covers:

Installing CAC reader support
Installing smart card middleware
Testing CAC reader functionality
Installing DoD PKI certificates
Configuring Firefox for CAC authentication
Testing access to DoD websites

1️⃣ Install Smart Card Middleware and CAC Reader Support

Linux uses middleware to communicate with CAC readers and smart cards. The most common and reliable package is OpenSC.

Open a terminal and install the required packages:

sudo apt update
sudo apt install opensc pcscd pcsc-tools libnss3-tools

What these packages do:

Package	Purpose
opensc	Smart card middleware
pcscd	Smart card daemon/service
pcsc-tools	CAC reader testing utilities
libnss3-tools	Firefox certificate tools
Enable the Smart Card Service

Start and enable the smart card service:

sudo systemctl enable pcscd --now

2️⃣ Test CAC Reader Detection

Before touching certificates or Firefox, confirm Linux can see the reader.

Run:

pcsc_scan

Expected result:

You should see:

Your CAC reader detected
ATR information from the inserted CAC card

Example output:

Reader 0: Identiv SCR3310
Card state: Card inserted
ATR: ...

If you see your reader and card:
✅ Linux hardware communication is working correctly.

Exit the scan utility with:

Ctrl + C

3️⃣ Download the DoD PKI Certificates

The DoD distributes certificates as PKCS#7 bundles (.p7b).

Download the DoD certificate bundle from the official DoD PKI repository.

The file will usually look similar to:

certificates_pkcs7_DoD.der.p7b

Place the file in your Downloads folder.

4️⃣ Convert the PKI Bundle into Linux-Compatible Certificates

Linux expects PEM/CRT certificates rather than PKCS#7 bundles.

Navigate to Downloads:

cd ~/Downloads

Verify the file exists:

ls *.p7b
Convert the PKCS#7 Bundle

Run:

openssl pkcs7 -print_certs -inform DER -in yourfile.der.p7b -out dod.pem

Replace:

yourfile.der.p7b

with your actual filename.

Verify the conversion worked:

head dod.pem

You should see:

-----BEGIN CERTIFICATE-----
5️⃣ Split the Certificates into Individual CRT Files

Create a folder for the certificates:

mkdir dod-certs

Split the PEM bundle:

csplit -z dod.pem '/-----BEGIN CERTIFICATE-----/' '{*}' -f dod-certs/cert- -b '%03d.crt'

Verify the files exist:

ls dod-certs

You should see multiple .crt files.

6️⃣ Install the DoD Certificates into the Linux Trust Store

Create a DoD certificate directory:

sudo mkdir -p /usr/local/share/ca-certificates/dod

Copy the certificates:

sudo cp dod-certs/*.crt /usr/local/share/ca-certificates/dod/

Update the trust store:

sudo update-ca-certificates

Expected output:

XX added, 0 removed

This means Linux now trusts DoD certificate authorities.

7️⃣ Configure Firefox for CAC Authentication

Firefox uses its own certificate and smart card system separate from the Linux OS.

Open Firefox Certificate Settings

Navigate to:

Settings → Privacy & Security → Certificates
Load the OpenSC PKCS#11 Module

Click:

Security Devices → Load

Enter:

Module Name
OpenSC
Module File
/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so

Click:

OK

If successful, you should now see:

OpenSC Smart Card Reader

listed in Security Devices.

8️⃣ Import DoD Certificates into Firefox (Optional but Recommended)

Some DoD sites work better when Firefox explicitly trusts the DoD CAs.

In Firefox:

Settings → Privacy & Security → Certificates → View Certificates

Select:

Authorities → Import

Navigate to your dod-certs folder and import the .crt files.

For each certificate:

✅ Check:

Trust this CA to identify websites
9️⃣ Restart Firefox

Close Firefox completely and reopen it.

Insert your CAC card before launching Firefox.

🔟 Test CAC Authentication

Try accessing:

https://milconnect.dmdc.osd.mil
https://web.mail.mil
https://portal.apps.mil

Expected behavior:

✅ Certificate selection popup
✅ Select your Authentication certificate
✅ Enter CAC PIN
✅ Successful login

Troubleshooting Tips
Firefox says “Unable to Add Module”

Usually means:

Incorrect PKCS#11 path
Firefox Flatpak/Snap sandbox issue
OpenSC not installed

Verify the module exists:

find /usr -name "opensc-pkcs11.so"
CAC Reader Not Detected

Verify services:

sudo systemctl status pcscd

Retest:

pcsc_scan
Certificates Not Installing

If update-ca-certificates says:

0 added, 0 removed

your certificates are probably still in .p7b or DER format and were not converted correctly.

Final Result

At this point your Pop!_OS system should support:

✅ CAC-enabled authentication
✅ Firefox smart card login
✅ DoD PKI trust
✅ Access to CAC-protected DoD portals

without relying on Windows InstallRoot or proprietary middleware.

Useful Commands Reference
Test CAC Reader
pcsc_scan
Restart Smart Card Service
sudo systemctl restart pcscd
Verify PKCS#11 Module Exists
find /usr -name "opensc-pkcs11.so"
Update Certificates
sudo update-ca-certificates
