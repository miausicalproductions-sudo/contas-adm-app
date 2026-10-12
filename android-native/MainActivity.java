package com.studiosmiau.contasadm;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(IgStoryPlugin.class);   // Stories: guardar a arte e abrir o editor do Instagram
        super.onCreate(savedInstanceState);
    }
}
