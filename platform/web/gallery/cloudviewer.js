// Minimaler WebGL-Punktwolken-Viewer (Three.js) fuer das kompakte .bin-Format
// aus scripts/pointcloud_web.py (float32 xyz + uint8 rgb, 15 Byte/Punkt).
// Marker werden als Billboard-Sprites an ihrer XYZ-Position gezeigt (relativ zum
// Scan-Ursprung, exakt wie die Panorama-Marker) und teilen dieselbe Klick-Logik.
//
// Zwei Navigationsarten: 'orbit' (Objekt von aussen betrachten) und 'walk' --
// First-Person mit Pointer-Lock, um zwischen den Baeumen frei umherzugehen,
// statt von Standpunkt zu Standpunkt zu springen.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const EYE = 1.7;            // Augenhoehe ueber Szenen-Boden (m)
const SPEED = 4.0;          // Gehgeschwindigkeit (m/s), Shift verdreifacht
const LOOK = 0.0022;        // rad je Pixel Mausbewegung
const PITCH_MAX = Math.PI / 2 - 0.02;

export class CloudViewer {
  constructor(container, onMarkerClick) {
    this.container = container;
    this.onMarkerClick = onMarkerClick;
    this.markerObjs = [];
    this.disposed = false;
    this.nav = 'orbit';
    this._keys = new Set();
    this._yaw = 0;
    this._pitch = 0;
    this._clock = new THREE.Clock();
    this._spawned = false;
    this._bbox = null;

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

    // Bodenraster: im Punktenebel die einzige verlaessliche Hoehen-/Richtungs-
    // referenz. Groesse folgt der Wolke, daher erst in _fitGround() erzeugt.
    this.ground = null;

    this.raycaster = new THREE.Raycaster();
    this.raycaster.params.Points.threshold = 0.3;
    this._pointer = new THREE.Vector2();
    this.renderer.domElement.addEventListener('pointerdown', (e) => this._onDown(e));
    this._onResize = () => this._resize();
    window.addEventListener('resize', this._onResize);

    this._onKeyDown = (e) => this._key(e, true);
    this._onKeyUp = (e) => this._key(e, false);
    this._onMouseMove = (e) => this._look(e);
    this._onLockChange = () => this._lockChanged();
    document.addEventListener('keydown', this._onKeyDown);
    document.addEventListener('keyup', this._onKeyUp);
    document.addEventListener('mousemove', this._onMouseMove);
    document.addEventListener('pointerlockchange', this._onLockChange);

    this._animate();
  }

  // ---- Navigation -------------------------------------------------------

  get locked() { return document.pointerLockElement === this.renderer.domElement; }

  setNav(mode) {
    if (mode === this.nav) return;
    this.nav = mode;
    this.controls.enabled = (mode === 'orbit');
    if (this.ground) this.ground.visible = (mode === 'walk');
    if (mode === 'walk') {
      // Blickrichtung der Orbit-Ansicht als Startpose uebernehmen, damit der
      // Wechsel nicht springt
      const dir = new THREE.Vector3();
      this.camera.getWorldDirection(dir);
      this._yaw = Math.atan2(dir.y, dir.x);
      this._pitch = Math.asin(THREE.MathUtils.clamp(dir.z, -1, 1));
      if (this._bbox) this.camera.position.z = this._bbox.min[2] + EYE;
      this._applyLook();
    } else {
      if (this.locked) document.exitPointerLock();
      this.controls.target.copy(this.camera.position).add(
        this.camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(8));
    }
    if (this.onNavChange) this.onNavChange(mode, this.locked);
  }

  requestLock() {
    if (this.nav === 'walk' && !this.locked) this.renderer.domElement.requestPointerLock();
  }

  _lockChanged() {
    if (this.onNavChange) this.onNavChange(this.nav, this.locked);
  }

  _key(e, down) {
    if (this.nav !== 'walk' || !this.locked) return;
    const c = e.code;
    if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft',
         'ArrowRight', 'Space', 'KeyC', 'ShiftLeft', 'ShiftRight'].includes(c)) {
      e.preventDefault();
      down ? this._keys.add(c) : this._keys.delete(c);
    }
  }

  _look(e) {
    if (this.nav !== 'walk' || !this.locked) return;
    this._yaw -= e.movementX * LOOK;
    this._pitch = THREE.MathUtils.clamp(this._pitch - e.movementY * LOOK,
                                        -PITCH_MAX, PITCH_MAX);
    this._applyLook();
  }

  _applyLook() {
    // Eigene Yaw/Pitch-Rechnung statt PointerLockControls: dessen YXZ-Euler
    // setzt Y=oben voraus, hier ist die Welt (wie im E57) Z-oben.
    const cp = Math.cos(this._pitch);
    const dir = new THREE.Vector3(Math.cos(this._yaw) * cp,
                                  Math.sin(this._yaw) * cp,
                                  Math.sin(this._pitch));
    this.camera.lookAt(this.camera.position.clone().add(dir));
  }

  _move(dt) {
    if (this.nav !== 'walk' || !this.locked || !this._keys.size) return;
    const k = this._keys;
    const fwd = (k.has('KeyW') || k.has('ArrowUp') ? 1 : 0)
              - (k.has('KeyS') || k.has('ArrowDown') ? 1 : 0);
    const side = (k.has('KeyD') || k.has('ArrowRight') ? 1 : 0)
               - (k.has('KeyA') || k.has('ArrowLeft') ? 1 : 0);
    const up = (k.has('Space') ? 1 : 0) - (k.has('KeyC') ? 1 : 0);
    if (!fwd && !side && !up) return;
    const v = SPEED * dt * (k.has('ShiftLeft') || k.has('ShiftRight') ? 3 : 1);
    // Vorwaerts bleibt waagerecht (auch beim Hochschauen) -- Hoehe nur ueber
    // Space/C, das laeuft sich deutlich vorhersehbarer als echtes Fliegen.
    const cy = Math.cos(this._yaw), sy = Math.sin(this._yaw);
    this.camera.position.x += (cy * fwd + sy * side) * v;
    this.camera.position.y += (sy * fwd - cy * side) * v;
    this.camera.position.z += up * v;
    this._applyLook();
  }

  _fitGround(meta) {
    const mn = meta.bbox_min, mx = meta.bbox_max;
    if (!mn || !mx) return;
    this._bbox = { min: mn, max: mx };
    if (this.ground) { this.scene.remove(this.ground); this.ground.geometry.dispose(); }
    const size = Math.ceil(Math.max(mx[0] - mn[0], mx[1] - mn[1]) + 20);
    this.ground = new THREE.GridHelper(size, Math.round(size / 2), 0x2b3440, 0x1b2129);
    this.ground.rotation.x = Math.PI / 2;                     // XY-Ebene (Z-oben)
    this.ground.position.set((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]);
    this.ground.visible = (this.nav === 'walk');
    this.scene.add(this.ground);

    if (!this._spawned) {
      this._spawned = true;
      // Startpunkt: am Suedrand der Wolke, Blick nach Norden ueber den Bestand
      this.camera.position.set((mn[0] + mx[0]) / 2, mn[1] - 6, mn[2] + EYE);
      this._yaw = Math.PI / 2;
      this._pitch = 0.15;
      this.controls.target.set((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2,
                               mn[2] + (mx[2] - mn[2]) * 0.4);
    }
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
    this._fitGround(meta);
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
    if (this.nav === 'walk' && !this.locked) { this.requestLock(); return; }
    const r = this.renderer.domElement.getBoundingClientRect();
    if (this.locked) {
      this._pointer.set(0, 0);            // im Pointer-Lock zaehlt das Fadenkreuz
    } else {
      this._pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
      this._pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    }
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
    const dt = Math.min(this._clock.getDelta(), 0.1);   // Tab-Wechsel abfedern
    if (this.nav === 'walk') this._move(dt);
    else this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this._raf);
    if (this._ro) this._ro.disconnect();
    if (this.locked) document.exitPointerLock();
    window.removeEventListener('resize', this._onResize);
    document.removeEventListener('keydown', this._onKeyDown);
    document.removeEventListener('keyup', this._onKeyUp);
    document.removeEventListener('mousemove', this._onMouseMove);
    document.removeEventListener('pointerlockchange', this._onLockChange);
    this.renderer.dispose();
    if (this.points) { this.points.geometry.dispose(); this.points.material.dispose(); }
    if (this.ground) this.ground.geometry.dispose();
    this.renderer.domElement.remove();
  }
}
