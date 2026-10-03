# Local 3D renderer

`three-orbit.min.js` bundles Three.js 0.180.0 and its OrbitControls under the
included MIT license. It exposes `window.THREE` plus `THREE.OrbitControls`.
The dashboard loads it as a classic local script, including from file://.
No runtime CDN or package manager is needed.

Built with esbuild 0.25.10 using this entry:

```js
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
window.THREE = { ...THREE, OrbitControls };
```

Build flags: `--bundle --format=iife --target=es2020 --minify --legal-comments=inline`.
Sources: https://github.com/mrdoob/three.js/tree/r180
