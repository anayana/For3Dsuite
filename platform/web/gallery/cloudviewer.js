// Minimaler WebGL-Punktwolken-Viewer (Three.js) fuer das kompakte .bin-Format
// aus scripts/pointcloud_web.py (float32 xyz + uint8 rgb, 15 Byte/Punkt).
// Marker werden als Billboard-Sprites an ihrer XYZ-Position gezeigt (relativ zum
// Scan-Ursprung, exakt wie die Panorama-Marker) und teilen dieselbe Klick-Logik.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export class CloudViewer {
  constructor(container, onMarkerClick) {
    this.container = container;
    this.onMarkerClick = onMarkerClick;
    this.markerObjs = [];
    this.disposed = false;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0d1117);
    this.camera = new THREE.PerspectiveCamera(
      60, container.clientWidth / container.clientHeight, 0.1, 2000);
    this.camera.up.set(0, 0, 1);                 // Welt-Z = oben (wie E57)
    this.camera.position.set(0, -0.1, 1.6);      // ~Augenhoehe am Scan-Ursprung

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    const [w0, h0] = this._size();
    this.renderer.setSize(w0, h0);
    container.appendChild(this.renderer.domElement);

    // Container wird beim Umschalten aus display:none sichtbar -> Groesse per
    // ResizeObserver nachziehen (clientWidth ist im versteckten Zustand 0).
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(container);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.target.set(2, 0, 1.3);

    this.raycaster = new THREE.Raycaster();
    this.raycaster.params.Points.threshold = 0.3;
    this._pointer = new THREE.Vector2();
    this.renderer.domElement.addEventListener('pointerdown', (e) => this._onDown(e));
    this._onResize = () => this._resize();
    window.addEventListener('resize', this._onResize);

    this._animate();
  }

  async loadBin(url, meta) {
    // Blockformat aus pointcloud_web.py: float32-xyz-Block, dann uint8-rgb-Block
    const ab = await (await fetch(url)).arrayBuffer();
    const n = meta.count;
    const positions = new Float32Array(ab, 0, n * 3);   // zero-copy
    const rgb = new Uint8Array(ab, n * 12, n * 3);
    const colors = new Float32Array(n * 3);
    for (let i = 0; i < n * 3; i++) colors[i] = rgb[i] / 255;

    if (this.points) {                                   // Stufen-Wechsel
      this.scene.remove(this.points);
      this.points.geometry.dispose();
      this.points.material.dispose();
      this.points = null;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.035, vertexColors: true,
      sizeAttenuation: true });
    this.points = new THREE.Points(geo, mat);
    this.scene.add(this.points);
  }

  setMarkers(markers, origin) {
    for (const m of this.markerObjs) this.scene.remove(m);
    this.markerObjs = [];
    for (const m of markers) {
      if (!m.xyz) continue;
      const spr = new THREE.Sprite(new THREE.SpriteMaterial({
        color: 0x7ee787, sizeAttenuation: true }));
      // Marker-XYZ ist absolut im Scan-KS -> auf den Ursprung zentrieren
      spr.position.set(m.xyz[0] - origin[0], m.xyz[1] - origin[1], m.xyz[2] - origin[2]);
      spr.scale.set(0.5, 0.5, 0.5);
      spr.userData.marker = m;
      this.scene.add(spr);
      this.markerObjs.push(spr);
    }
  }

  _onDown(ev) {
    const r = this.renderer.domElement.getBoundingClientRect();
    this._pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    this._pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    this.raycaster.setFromCamera(this._pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.markerObjs, false)[0];
    if (hit && this.onMarkerClick) this.onMarkerClick(hit.object.userData.marker);
  }

  _size() {
    // Fallback auf Fenstergroesse, falls der Container (noch) keine Layout-Groesse hat
    const w = this.container.clientWidth || window.innerWidth || 800;
    const h = this.container.clientHeight || window.innerHeight || 600;
    return [w, h];
  }

  _resize() {
    if (this.disposed) return;
    const [w, h] = this._size();
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  _animate() {
    if (this.disposed) return;
    this._raf = requestAnimationFrame(() => this._animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this._raf);
    if (this._ro) this._ro.disconnect();
    window.removeEventListener('resize', this._onResize);
    this.renderer.dispose();
    if (this.points) { this.points.geometry.dispose(); this.points.material.dispose(); }
    this.renderer.domElement.remove();
  }
}
