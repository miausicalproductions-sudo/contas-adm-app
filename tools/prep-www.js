// Monta a pasta www do app de celular: carregador + painel
const fs = require('fs'), path = require('path');
const root = path.join(__dirname, '..'), www = path.join(root, 'www');
fs.rmSync(www, { recursive: true, force: true }); fs.mkdirSync(www);
fs.copyFileSync(path.join(root, 'mobile', 'index.html'), path.join(www, 'index.html'));
fs.copyFileSync(path.join(root, 'app', 'painel.html'), path.join(www, 'painel.html'));
fs.copyFileSync(path.join(root, 'build', 'icon-512.png'), path.join(www, 'icon.png'));
console.log('www pronto');
