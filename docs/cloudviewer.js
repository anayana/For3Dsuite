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

// QSM-Segmentklassen: Stamm (Ordnung 1) / Ast (2-3) / Zweig (>=4).
// Klare, kraeftige Farben statt eines feinen Verlaufs, damit die Segmentierung
// im Modell sofort erkennbar ist.
const QSM_CLASSES = [
  { name: 'Stamm', color: [155, 100, 60] },     // braun
  { name: 'Ast', color: [235, 150, 55] },       // orange
  { name: 'Zweig', color: [110, 205, 110] },    // gruen
];
const QSM_CLASS_IDX = (o) => (o <= 1 ? 0 : (o <= 3 ? 1 : 2));
const QSM_CLASS_COLOR = (o) => QSM_CLASSES[QSM_CLASS_IDX(o)].color;
const QSM_CLASS_NAME = (o) => QSM_CLASSES[QSM_CLASS_IDX(o)].name;

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
    // Blockformat aus pointcloud_web.py: float32-xyz-Block, dann uint8-rgb-Block.
    // Optional folgt ein uint16-Block mit der Segment-ID je Punkt (meta.segmented),
    // damit die Wolke im Browser nach Kennwert umgefaerbt werden kann.
    const ab = await (await fetch(url)).arrayBuffer();
    const n = meta.count;
    const positions = new Float32Array(ab, 0, n * 3);   // zero-copy
    const rgb = new Uint8Array(ab, n * 12, n * 3);
    const colors = new Float32Array(n * 3);
    for (let i = 0; i < n * 3; i++) colors[i] = rgb[i] / 255;

    // Segment-ID-Spur nur lesen, wenn deklariert UND wirklich im Puffer (der
    // uint16-Block ist ggf. nicht an 2 Byte ausgerichtet -> kopieren, nicht mappen)
    this.segids = null;
    if (meta.segmented && ab.byteLength >= n * 15 + n * 2) {
      this.segids = new Uint16Array(new Uint8Array(ab, n * 15, n * 2).slice().buffer);
    }
    this._baseColors = colors.slice();   // fuer Rueckkehr zur Grundeinfaerbung

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

  // QSM-Zylindermodell laden und als InstancedMesh rendern. Format der .bin:
  // float32-Bloecke Start n*3, Ende n*3, Radius n, dann uint8 Ordnung n.
  async loadQSM(url, meta) {
    const raw = await (await fetch(url)).arrayBuffer();
    const n = meta.count;
    const S = new Float32Array(raw, 0, n * 3);
    const E = new Float32Array(raw, n * 12, n * 3);
    const R = new Float32Array(raw, n * 24, n);
    const O = new Uint8Array(raw, n * 28, n);
    const omax = meta.order_max || 8;

    // Wenig Radialsegmente (6) -- bei ~60k Instanzen zaehlt jeder Dreieckszug.
    const geo = new THREE.CylinderGeometry(1, 1, 1, 6, 1, true);
    // KEIN vertexColors: die Zylindergeometrie hat kein color-Attribut, dann
    // multipliziert der Shader mit (0,0,0) -> alles schwarz. Die Per-Instanz-
    // Farbe (instanceColor, unten via setColorAt) greift bei InstancedMesh von
    // selbst (USE_INSTANCING_COLOR).
    const mat = new THREE.MeshBasicMaterial();
    const mesh = new THREE.InstancedMesh(geo, mat, n);
    const up = new THREE.Vector3(0, 1, 0);
    const s = new THREE.Vector3(), e = new THREE.Vector3(), dir = new THREE.Vector3();
    const mid = new THREE.Vector3(), q = new THREE.Quaternion();
    const scl = new THREE.Vector3(), m = new THREE.Matrix4();
    const col = new THREE.Color();
    for (let i = 0; i < n; i++) {
      s.set(S[3*i], S[3*i+1], S[3*i+2]);
      e.set(E[3*i], E[3*i+1], E[3*i+2]);
      const L = dir.subVectors(e, s).length() || 1e-4;
      mid.addVectors(s, e).multiplyScalar(0.5);
      q.setFromUnitVectors(up, dir.normalize());
      // Mindestradius je Klasse, damit auch feine Zweige sichtbar bleiben
      // (echte Radien sind teils <1 px). Reihenfolge Stamm > Ast > Zweig.
      const o = O[i];
      const minR = o <= 1 ? 0.02 : (o <= 3 ? 0.012 : 0.008);
      const r = Math.max(R[i], minR);
      scl.set(r, L, r);
      m.compose(mid, q, scl);
      mesh.setMatrixAt(i, m);
      // KATEGORIALE Segmentierung: Stamm / Ast / Zweig in klaren Farben.
      const c = QSM_CLASS_COLOR(o);
      mesh.setColorAt(i, col.setRGB(c[0] / 255, c[1] / 255, c[2] / 255));
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;

    if (this.qsm) { this.scene.remove(this.qsm); this.qsm.geometry.dispose(); }
    this.qsm = mesh;
    this.qsm.visible = false;                 // Default: Punkte zeigen
    this.scene.add(this.qsm);

    // Zylinderdaten fuer das Anklicken behalten. ACHTUNG: die .bin verkettet
    // MEHRERE Baeume eines Plots -> baumweite Summen (Stammlaenge, Kronenansatz)
    // waeren hier falsch. Ganzbaum-QSM-Werte haengen je Baum am Marker
    // (QSM_Holzvolumen etc.). Hier nur Segment-Kennzahlen + ein Plot-Bodenniveau
    // fuer die relative Hoehe.
    let zmin = Infinity;
    const len = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const L = Math.hypot(E[3*i] - S[3*i], E[3*i+1] - S[3*i+1], E[3*i+2] - S[3*i+2]);
      len[i] = L;
      zmin = Math.min(zmin, S[3*i+2], E[3*i+2]);
    }
    this._qsm = { S, E, R, O, len, n, omax, zmin };
  }

  // Kennzahlen eines angeklickten Zylinders (Segment). Ganzbaum-Werte kommen
  // ueber den Marker, weil die .bin mehrere Baeume enthaelt.
  _qsmInfo(i) {
    const q = this._qsm; if (!q || i == null || i < 0 || i >= q.n) return null;
    const o = q.O[i], L = q.len[i], r = q.R[i];
    return {
      order: o,
      is_trunk: o <= 1,
      klasse: QSM_CLASS_NAME(o),
      diameter_cm: 2 * r * 100,
      length_m: L,
      segment_volume_l: Math.PI * r * r * L * 1000,
      z_from_ground_m: (q.S[3*i+2] + q.E[3*i+2]) / 2 - q.zmin,
    };
  }

  setQSMVisible(v) { if (this.qsm) this.qsm.visible = v; }
  setPointsVisible(v) { if (this.points) this.points.visible = v; }

  // Punktwolke nach Segment umfaerben. segColor: {segid -> [r,g,b] in 0..255}.
  // Punkte ohne Segment (id 0) oder ohne Eintrag behalten ihre Grundfarbe --
  // so bleibt die Kulisse gedaempft, waehrend nur die Hecke die Wertfarbe traegt.
  recolorBySegment(segColor) {
    if (!this.points || !this.segids || !this._baseColors) return;
    const col = this.points.geometry.attributes.color;
    const a = col.array, base = this._baseColors, seg = this.segids;
    for (let i = 0, n = seg.length; i < n; i++) {
      const c = segColor[seg[i]];
      if (c) { a[3*i] = c[0] / 255; a[3*i+1] = c[1] / 255; a[3*i+2] = c[2] / 255; }
      else   { a[3*i] = base[3*i]; a[3*i+1] = base[3*i+1]; a[3*i+2] = base[3*i+2]; }
    }
    col.needsUpdate = true;
  }

  resetColors() {
    if (!this.points || !this._baseColors) return;
    this.points.geometry.attributes.color.array.set(this._baseColors);
    this.points.geometry.attributes.color.needsUpdate = true;
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
    if (hit && this.onMarkerClick) { this.onMarkerClick(hit.object.userData.marker); return; }
    // Sonst: sichtbares QSM-Zylindermodell anklickbar (Stamm/Ast-Kennzahlen)
    if (this.qsm && this.qsm.visible && this._qsm && this.onQSMPick) {
      const qh = this.raycaster.intersectObject(this.qsm, false)[0];
      if (qh && qh.instanceId != null) {
        const info = this._qsmInfo(qh.instanceId);
        if (info) this.onQSMPick(info);
      }
    }
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
    if (this.qsm) { this.qsm.geometry.dispose(); this.qsm.material.dispose(); }
    if (this.ground) this.ground.geometry.dispose();
    this.renderer.domElement.remove();
  }
}
