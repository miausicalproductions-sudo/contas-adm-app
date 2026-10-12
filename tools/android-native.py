# Coloca no projeto Android o recurso nativo dos Stories (guardar a arte e abrir o editor de Stories do Instagram)
import os, shutil
root = os.path.join(os.path.dirname(__file__), '..')
src = os.path.join(root, 'android-native')
main = os.path.join(root, 'android', 'app', 'src', 'main')
pkg = os.path.join(main, 'java', 'com', 'studiosmiau', 'contasadm'); os.makedirs(pkg, exist_ok=True)
for f in ('IgStoryPlugin.java', 'MainActivity.java'): shutil.copy(os.path.join(src, f), os.path.join(pkg, f))
xml = os.path.join(main, 'res', 'xml'); os.makedirs(xml, exist_ok=True); shutil.copy(os.path.join(src, 'file_paths.xml'), os.path.join(xml, 'file_paths.xml'))
man = os.path.join(main, 'AndroidManifest.xml'); m = open(man).read()
if 'com.instagram.android' not in m:
    m = m.replace('<application', '<queries>\n        <package android:name="com.instagram.android" />\n        <intent><action android:name="com.instagram.share.ADD_TO_STORY" /></intent>\n    </queries>\n\n    <application', 1)
if 'androidx.core.content.FileProvider' not in m:
    m = m.replace('</application>', '        <provider android:name="androidx.core.content.FileProvider" android:authorities="${applicationId}.fileprovider" android:exported="false" android:grantUriPermissions="true">\n            <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/file_paths" />\n        </provider>\n    </application>', 1)
open(man, 'w').write(m)
print('recurso dos Stories ok')
