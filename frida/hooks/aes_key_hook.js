/**
 * AES Key Extraction Hook for Free Fire
 * Hooks AES encryption/decryption to extract the current game keys.
 * 
 * Usage:
 *   frida -U -n Gadget -l aes_key_hook.js
 */

function hookAES() {
    console.log("[*] Searching for AES encryption functions...");

    // Common AES function signatures in Il2Cpp
    var aesEncrypt = Module.findExportByName(null, 
        "_ZN6Crypto3AES7EncryptEPKhS2_i");

    if (!aesEncrypt) {
        // Try alternative signatures
        var modules = Process.enumerateModules();
        for (var i = 0; i < modules.length; i++) {
            var mod = modules[i];
            if (mod.name.includes("freefire") || mod.name.includes("game")) {
                var exports = Module.enumerateExports(mod.name);
                for (var j = 0; j < exports.length; j++) {
                    var exp = exports[j];
                    if (exp.name.toLowerCase().includes("aes") && 
                        exp.name.toLowerCase().includes("encrypt")) {
                        aesEncrypt = exp.address;
                        console.log("[+] Found AES encrypt: " + exp.name + " @ " + aesEncrypt);
                        break;
                    }
                }
            }
        }
    }

    if (aesEncrypt) {
        Interceptor.attach(aesEncrypt, {
            onEnter: function(args) {
                // args[0] = key, args[1] = iv, args[2] = data
                this.key = Memory.readByteArray(args[0], 16);
                this.iv = Memory.readByteArray(args[1], 16);

                var keyHex = hexdump(this.key, {length: 16, header: false}).replace(/\s/g, "");
                var ivHex = hexdump(this.iv, {length: 16, header: false}).replace(/\s/g, "");

                console.log("[+] AES Key captured:");
                console.log("    Key: " + keyHex);
                console.log("    IV:  " + ivHex);

                // Save to file
                var file = new java.io.File("/sdcard/ff_aes_keys.json");
                var writer = new java.io.FileWriter(file);
                writer.write(JSON.stringify({
                    key: keyHex,
                    iv: ivHex,
                    captured_at: new Date().toISOString(),
                    version: "OB53"
                }, null, 2));
                writer.close();
            }
        });
    }

    // Hook OpenSSL AES functions as fallback
    var EVP_CipherInit_ex = Module.findExportByName(null, "EVP_CipherInit_ex");
    if (EVP_CipherInit_ex) {
        Interceptor.attach(EVP_CipherInit_ex, {
            onEnter: function(args) {
                if (args[2].isNull()) return;
                var key = Memory.readByteArray(args[3], 16);
                var iv = Memory.readByteArray(args[4], 16);
                if (key && iv) {
                    console.log("[+] OpenSSL AES Key:");
                    console.log("    Key: " + hexdump(key, {length: 16, header: false}));
                }
            }
        });
    }
}

if (Java.available) {
    Java.perform(function() {
        console.log("[*] Java runtime ready");
        hookAES();
    });
} else {
    hookAES();
}
