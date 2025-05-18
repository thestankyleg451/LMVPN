import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--noconsole',
    '--windowed',
    '--icon=cat1.icns',
    '--clean',
    '--hidden-import', 'PyQt5.sip',
    '--hidden-import', 'PyQt5.QtWebEngineWidgets',
    '--exclude-module', 'joblib',
    '--add-data', 'working_proxies_cache.txt:.',
    '--add-data', 'proxies_cache.json:.'
])