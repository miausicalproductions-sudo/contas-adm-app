package com.studiosmiau.contasadm;

import android.content.Intent;
import android.net.Uri;
import android.util.Base64;
import androidx.core.content.FileProvider;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;
import java.io.FileOutputStream;

// Contas ADM: guarda as artes dos Stories no aparelho e abre o editor de Stories do Instagram já com a arte.
@CapacitorPlugin(name = "IgStory")
public class IgStoryPlugin extends Plugin {
    private File dir() { File d = new File(getContext().getCacheDir(), "stories"); d.mkdirs(); return d; }
    private static String clean(String n) { return n == null ? "arte" : n.replaceAll("[^\\w.-]", "_"); }

    @PluginMethod
    public void has(PluginCall call) {
        File f = new File(dir(), clean(call.getString("name")));
        JSObject r = new JSObject(); r.put("ok", f.exists() && f.length() > 0); r.put("path", f.getAbsolutePath()); call.resolve(r);
    }

    @PluginMethod
    public void save(PluginCall call) {
        String data = call.getString("data");
        if (data == null) { call.reject("faltou o arquivo"); return; }
        try {
            File f = new File(dir(), clean(call.getString("name")));
            FileOutputStream o = new FileOutputStream(f); o.write(Base64.decode(data, Base64.DEFAULT)); o.close();
            long lim = System.currentTimeMillis() - 4L * 86400000L;          // faxina: artes com mais de 4 dias
            File[] all = dir().listFiles(); if (all != null) for (File x : all) if (x.lastModified() < lim) x.delete();
            JSObject r = new JSObject(); r.put("ok", true); r.put("path", f.getAbsolutePath()); call.resolve(r);
        } catch (Exception e) { call.reject("não consegui guardar a arte: " + e.getMessage()); }
    }

    @PluginMethod
    public void share(PluginCall call) {
        String path = call.getString("path"), type = call.getString("type", "image/*"), appId = call.getString("appId", "");
        File f = path == null ? null : new File(path);
        if (f == null || !f.exists()) { call.reject("arte não encontrada no aparelho"); return; }
        Uri uri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", f);
        Intent i = new Intent("com.instagram.share.ADD_TO_STORY");
        i.putExtra("source_application", appId);
        i.setDataAndType(uri, type);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        i.setPackage("com.instagram.android");
        try {
            getActivity().grantUriPermission("com.instagram.android", uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            getActivity().startActivity(i);
            call.resolve();
        } catch (Exception e) {                                                // Instagram sem esse recurso: abre o "compartilhar" do Android
            try {
                Intent s = new Intent(Intent.ACTION_SEND); s.setType(type); s.putExtra(Intent.EXTRA_STREAM, uri); s.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                getActivity().startActivity(Intent.createChooser(s, "Mandar para"));
                call.resolve();
            } catch (Exception e2) { call.reject("não consegui abrir o Instagram: " + e2.getMessage()); }
        }
    }
}
