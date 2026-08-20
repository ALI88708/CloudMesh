const esbuild = require('esbuild');
const path = require('path');
const fs = require('fs');

const distDir = path.join(__dirname, 'dist');
const rendererDist = path.join(distDir, 'renderer');

// Clean dist
if (fs.existsSync(distDir)) fs.rmSync(distDir, { recursive: true });
fs.mkdirSync(distDir, { recursive: true });
fs.mkdirSync(rendererDist, { recursive: true });

async function build() {
  // 1. Bundle main process (includes privacy.ts)
  await esbuild.build({
    entryPoints: [path.join(__dirname, 'src', 'main.ts')],
    bundle: true,
    platform: 'node',
    target: 'node20',
    outfile: path.join(distDir, 'main.js'),
    external: ['electron'],
    format: 'cjs',
    sourcemap: false,
    minify: false
  });
  console.log('✓ main.js');

  // 2. Bundle preload
  await esbuild.build({
    entryPoints: [path.join(__dirname, 'src', 'preload.ts')],
    bundle: true,
    platform: 'node',
    target: 'node20',
    outfile: path.join(distDir, 'preload.js'),
    external: ['electron'],
    format: 'cjs',
    sourcemap: false,
    minify: false
  });
  console.log('✓ preload.js');

  // 3. Bundle renderer (i18n + themes + renderer together)
  await esbuild.build({
    entryPoints: [path.join(__dirname, 'src', 'renderer', 'renderer.ts')],
    bundle: true,
    platform: 'browser',
    target: 'es2020',
    outfile: path.join(rendererDist, 'renderer.js'),
    format: 'iife',
    sourcemap: false,
    minify: false
  });
  console.log('✓ renderer/renderer.js');

  // 4. Copy static files to dist/renderer/
  const staticFiles = ['index.html', 'styles.css', 'logo.png'];
  for (const file of staticFiles) {
    const src = path.join(__dirname, 'renderer', file);
    const dst = path.join(rendererDist, file);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, dst);
      console.log(`✓ renderer/${file}`);
    }
  }

  // 5. Copy assets
  const assetsDir = path.join(__dirname, 'assets');
  const assetsDist = path.join(distDir, 'assets');
  if (fs.existsSync(assetsDir)) {
    fs.cpSync(assetsDir, assetsDist, { recursive: true });
    console.log('✓ assets/');
  }

  // 6. Copy privacy-preload.js to dist/
  const ppSrc = path.join(__dirname, 'privacy-preload.js');
  if (fs.existsSync(ppSrc)) {
    fs.copyFileSync(ppSrc, path.join(distDir, 'privacy-preload.js'));
    console.log('✓ privacy-preload.js');
  }

  // 7. Copy package.json to dist/ (for Electron)
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
  pkg.main = 'main.js';
  fs.writeFileSync(path.join(distDir, 'package.json'), JSON.stringify(pkg, null, 2));
  console.log('✓ dist/package.json');

  console.log('\nBuild complete! Run: cd dist && npx electron .');
}

build().catch(err => {
  console.error('Build failed:', err);
  process.exit(1);
});
