# TaleemPK release signing

The 5.0.0 final universal APK is signed with the TaleemPK release certificate,
not the automatically generated Android Debug certificate used by CI candidates.
The app payload matches the previously tested 5.0.0+500 build.

Release certificate SHA-256:
`7062a059843855c93ecd3ae323d01872f3d72bc172142ac27bd4f9c453838691`

The private key and password are deliberately outside this repository. The owner
must keep the private signing backup; losing it prevents compatible updates.
Never upload the backup to a public repository or distribute it with the app.

To sign a subsequent compiled release APK, restore the existing private backup
to a protected directory and run:

```sh
python3 tools/sign_release.py --sdk-tools /path/to/android-build-tools \
  --key-dir /private/taleempk-signing \
  --input /path/to/build.apk --output /path/to/release.apk
```

The script expects `apksigner.jar`, `aapt2` and `zipalign` in the tools directory.
It refuses a debuggable app, preserves the input, applies 16 KB ZIP alignment,
verifies v2/v3 signatures, checks the certificate, and confirms unchanged app
payload plus all three native ABIs. Future code updates must increment the
Android versionCode above 500 and reuse this exact release key.

This key cannot update earlier installations signed with an unrelated debug key.
The old private key is unavailable, so a signed rotation lineage cannot be made.
Do not instruct users to delete app data to hide this limitation.

Signing does not configure SMTP, Firebase, realtime infrastructure or production
server settings. Those services require separate live deployment verification.
