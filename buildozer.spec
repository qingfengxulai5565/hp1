[app]
title = Harmony Player
package.name = harmonyplayer
package.domain = org.harmony
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf
main = main.py
requirements = python3,kivy==2.1.0,mutagen,android
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
orientation = portrait
log_level = 2
android.api = 31
android.minapi = 21
android.sdk = 33
android.ndk = 23b
android.ndk_api = 21
android.arch = arm64-v8a