/**
 * Guest Account Capture Hook
 * Extracts guest UIDs and passwords during registration/login.
 * 
 * Usage:
 *   frida -U -n Gadget -l guest_hook.js
 */

var OUTPUT_FILE = "/sdcard/ff_guests.json";

function saveGuest(uid, password, token) {
    var data = {
        uid: uid,
        password: password,
        token: token || "",
        captured_at: new Date().toISOString(),
        region: "ME"
    };

    Java.perform(function() {
        try {
            var file = new java.io.File(OUTPUT_FILE);
            var existing = [];

            if (file.exists()) {
                var reader = new java.io.BufferedReader(new java.io.FileReader(file));
                var content = "";
                var line;
                while ((line = reader.readLine()) != null) content += line;
                reader.close();
                try { existing = JSON.parse(content); } catch(e) {}
                if (!Array.isArray(existing)) existing = [];
            }

            var exists = existing.some(function(g) { return g.uid === uid; });
            if (!exists) {
                existing.push(data);
                var writer = new java.io.FileWriter(file);
                writer.write(JSON.stringify(existing, null, 2));
                writer.close();
                console.log("[+] Guest saved: " + uid);
            }
        } catch(e) {
            console.log("[-] Save error: " + e);
        }
    });
}

function hookSharedPrefs() {
    Java.perform(function() {
        var Editor = Java.use("android.app.SharedPreferencesImpl$EditorImpl");

        Editor.putString.overload('java.lang.String', 'java.lang.String').implementation = function(key, value) {
            var k = key.toString();
            var v = value ? value.toString() : "";

            if (k.includes("guest_uid") || k.includes("uid")) {
                this._guestUid = v;
                console.log("[*] UID captured: " + v);
            }
            if (k.includes("guest_password") || k.includes("password")) {
                this._guestPassword = v;
                console.log("[*] Password captured");
            }
            if (k.includes("token") || k.includes("auth")) {
                this._guestToken = v;
            }

            if (this._guestUid && this._guestPassword) {
                saveGuest(this._guestUid, this._guestPassword, this._guestToken);
                this._guestUid = null;
                this._guestPassword = null;
            }

            return this.putString(key, value);
        };

        console.log("[*] SharedPreferences hooks installed");
    });
}

function hookNativeCrypto() {
    // Hook native crypto functions that handle guest credentials
    var modules = Process.enumerateModules();
    for (var i = 0; i < modules.length; i++) {
        var mod = modules[i];
        if (mod.name.includes("freefire")) {
            console.log("[*] Scanning module: " + mod.name);
            // Add native hooks here if needed
        }
    }
}

hookSharedPrefs();
hookNativeCrypto();
