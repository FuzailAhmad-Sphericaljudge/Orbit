import { useEffect, useRef } from "react";
import * as THREE from "three";
import { buildCommanderGeometry, type CommanderMode } from "./CommanderAvatar";

export type SpatialModule = {
  id: string;
  index: string;
  title: string;
  eyebrow: string;
  summary: string;
  metric: string;
  metricLabel: string;
  accent: string;
  accentSecondary: string;
  visual: "voice" | "evidence" | "timeline" | "actions" | "graph" | "prediction" | "systems" | "recovery" | "report";
};

type Props = {
  modules: SpatialModule[];
  mode: CommanderMode;
  onActiveChange: (index: number) => void;
  onOpen: (id: string) => void;
};

function seeded(seed: number) {
  let value = seed >>> 0;
  return () => ((value = (value * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function hexToRgb(hex: string) {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
}

function rgba(hex: string, alpha: number) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function drawVisual(context: CanvasRenderingContext2D, module: SpatialModule, seedValue: number) {
  const random = seeded(seedValue);
  context.shadowColor = rgba(module.accent, .8);
  context.shadowBlur = 18;
  context.strokeStyle = rgba(module.accent, .88);
  context.fillStyle = rgba(module.accentSecondary, .72);
  context.lineWidth = 2;
  if (module.visual === "voice") {
    context.beginPath();
    for (let x = 76; x < 948; x += 8) {
      const envelope = Math.sin(((x - 76) / 872) * Math.PI);
      const y = 390 + Math.sin(x * .075) * 70 * envelope + Math.sin(x * .19) * 22 * envelope;
      x === 76 ? context.moveTo(x, y) : context.lineTo(x, y);
    }
    context.stroke();
  } else if (module.visual === "evidence" || module.visual === "graph") {
    const points = Array.from({ length: module.visual === "graph" ? 38 : 24 }, () => ({ x: 90 + random() * 830, y: 265 + random() * 255 }));
    for (let index = 0; index < points.length * 1.4; index += 1) {
      const a = points[Math.floor(random() * points.length)];
      const b = points[Math.floor(random() * points.length)];
      context.globalAlpha = .24;
      context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y); context.stroke();
    }
    context.globalAlpha = 1;
    for (const point of points) { context.beginPath(); context.arc(point.x, point.y, 2 + random() * 4, 0, Math.PI * 2); context.fill(); }
  } else if (module.visual === "timeline") {
    for (let index = 0; index < 14; index += 1) {
      const x = 85 + index * 65;
      const height = 30 + random() * 190;
      context.globalAlpha = .25 + random() * .5;
      context.fillRect(x, 525 - height, 3, height);
      context.fillRect(x - 3, 525 - height, 9, 3);
    }
    context.globalAlpha = 1;
  } else if (module.visual === "actions") {
    for (let index = 0; index < 7; index += 1) {
      const y = 278 + index * 42;
      context.globalAlpha = .65;
      context.strokeRect(80, y, 14, 14);
      context.fillRect(120, y + 5, 340 + random() * 420, 2);
    }
    context.globalAlpha = 1;
  } else if (module.visual === "prediction") {
    const curves = [[.035, 390], [.048, 430], [.062, 470]];
    for (const [growth, start] of curves) {
      context.beginPath();
      for (let x = 80; x <= 940; x += 10) {
        const t = (x - 80) / 860;
        const y = start - Math.pow(t, 1.7) * growth * 3400 + Math.sin(t * 9) * 5;
        x === 80 ? context.moveTo(x, y) : context.lineTo(x, y);
      }
      context.stroke();
    }
    for (let index = 0; index < 8; index += 1) {
      context.globalAlpha = .3 + index * .07;
      context.beginPath(); context.arc(135 + index * 105, 480 - index * 27, 5 + index * .8, 0, Math.PI * 2); context.fill();
    }
    context.globalAlpha = 1;
  } else if (module.visual === "systems") {
    for (let row = 0; row < 3; row += 1) for (let col = 0; col < 5; col += 1) {
      context.globalAlpha = .18 + random() * .45;
      context.strokeRect(90 + col * 175, 275 + row * 85, 128, 52);
    }
    context.globalAlpha = 1;
  } else if (module.visual === "recovery") {
    for (let index = 0; index < 9; index += 1) {
      context.globalAlpha = .2 + index * .07;
      context.fillRect(80 + index * 97, 505 - index * 19, 68, index * 19 + 4);
    }
    context.globalAlpha = 1;
  } else {
    context.font = "400 90px Georgia";
    context.fillStyle = "rgba(196, 215, 220, .22)";
    context.fillText("AFTER", 74, 390);
    context.fillText("ACTION", 390, 485);
  }
}

function createTexture(module: SpatialModule, index: number) {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 680;
  const context = canvas.getContext("2d")!;
  const background = context.createLinearGradient(0, 0, canvas.width, canvas.height);
  background.addColorStop(0, rgba(module.accent, .25));
  background.addColorStop(.42, "rgba(12, 18, 34, .96)");
  background.addColorStop(1, rgba(module.accentSecondary, .2));
  context.fillStyle = background;
  context.fillRect(0, 0, canvas.width, canvas.height);
  const glow = context.createRadialGradient(760, 330, 10, 760, 330, 470);
  glow.addColorStop(0, rgba(module.accentSecondary, .2));
  glow.addColorStop(1, rgba(module.accentSecondary, 0));
  context.fillStyle = glow;
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = rgba(module.accent, .82);
  context.lineWidth = 2;
  context.strokeRect(22, 22, 980, 636);
  context.fillStyle = rgba(module.accent, 1);
  context.font = "400 17px Consolas";
  context.fillText(`${module.index} / ${module.eyebrow.toUpperCase()}`, 64, 72);
  context.textAlign = "right";
  context.fillText(module.metricLabel.toUpperCase(), 960, 72);
  context.textAlign = "left";
  context.fillStyle = "rgba(249, 250, 255, 1)";
  context.font = "400 76px Georgia";
  context.fillText(module.title, 62, 190);
  context.fillStyle = rgba(module.accentSecondary, 1);
  context.font = "400 60px Georgia";
  context.textAlign = "right";
  context.fillText(module.metric, 958, 185);
  context.textAlign = "left";
  drawVisual(context, module, 631 + index * 97);
  context.shadowBlur = 0;
  context.fillStyle = "rgba(218, 228, 242, .9)";
  context.font = "400 16px Arial";
  const line = module.summary.length > 88 ? `${module.summary.slice(0, 85)}...` : module.summary;
  context.fillText(line, 62, 616);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

function curvedPanelGeometry() {
  const geometry = new THREE.PlaneGeometry(3.7, 2.46, 32, 10);
  const positions = geometry.attributes.position;
  for (let index = 0; index < positions.count; index += 1) {
    const x = positions.getX(index);
    positions.setZ(index, -.065 * x * x);
  }
  positions.needsUpdate = true;
  geometry.computeVertexNormals();
  return geometry;
}

export function SpatialCommandCenter({ modules, mode, onActiveChange, onOpen }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    const container = host.current;
    if (!container) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x080b19, .046);
    const camera = new THREE.PerspectiveCamera(42, 1, .1, 100);
    camera.position.set(0, .1, 8.2);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
    renderer.setClearColor(0x080b19, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    const grid = new THREE.GridHelper(42, 42, 0x7048e8, 0x174d61);
    grid.position.set(0, -2.15, -4);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = .72;
    scene.add(grid);

    const faceGeometry = buildCommanderGeometry();
    const faceMaterial = new THREE.PointsMaterial({ color: 0x9b7bff, size: .013, transparent: true, opacity: .4, blending: THREE.AdditiveBlending, depthWrite: false });
    const featureMaterial = new THREE.PointsMaterial({ color: 0x58f5c7, size: .019, transparent: true, opacity: .72, blending: THREE.AdditiveBlending, depthWrite: false });
    const face = new THREE.Group();
    face.add(new THREE.Points(faceGeometry.silhouette, faceMaterial), new THREE.Points(faceGeometry.features, featureMaterial));
    face.position.set(0, .2, -3.2);
    face.scale.setScalar(1.25);
    scene.add(face);

    const panelGeometry = curvedPanelGeometry();
    const textures = modules.map(createTexture);
    const panels = modules.map((module, index) => {
      const material = new THREE.MeshBasicMaterial({ map: textures[index], transparent: true, opacity: 1, side: THREE.DoubleSide, depthWrite: true });
      const mesh = new THREE.Mesh(panelGeometry, material);
      mesh.userData = { index, id: module.id };
      scene.add(mesh);
      return mesh;
    });

    let active = 0;
    let target = 0;
    let dragging = false;
    let moved = false;
    let dragX = 0;
    let pointerX = 0;
    let pointerY = 0;
    let animationFrame = 0;
    const pointer = new THREE.Vector2();
    const raycaster = new THREE.Raycaster();
    const clock = new THREE.Clock();

    const clampTarget = () => { target = THREE.MathUtils.clamp(target, 0, modules.length - 1); };
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      target += Math.sign(event.deltaY || event.deltaX) * .72;
      clampTarget();
    };
    const onPointerDown = (event: PointerEvent) => { dragging = true; moved = false; dragX = event.clientX; container.setPointerCapture(event.pointerId); };
    const onPointerMove = (event: PointerEvent) => {
      pointerX = (event.clientX / innerWidth - .5) * 2;
      pointerY = (event.clientY / innerHeight - .5) * 2;
      if (!dragging) return;
      const delta = event.clientX - dragX;
      if (Math.abs(delta) > 2) moved = true;
      target -= delta * .0036;
      dragX = event.clientX;
      clampTarget();
    };
    const onPointerUp = (event: PointerEvent) => {
      dragging = false;
      target = Math.round(target);
      clampTarget();
      if (moved) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(panels, false)[0]?.object as THREE.Mesh | undefined;
      if (!hit) return;
      const index = hit.userData.index as number;
      if (Math.abs(active - index) > .28) target = index;
      else onOpen(hit.userData.id as string);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") target += 1;
      else if (event.key === "ArrowLeft") target -= 1;
      else if (event.key === "Enter") onOpen(modules[Math.round(active)].id);
      else return;
      target = Math.round(target);
      clampTarget();
    };

    container.addEventListener("wheel", onWheel, { passive: false });
    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerUp);
    window.addEventListener("keydown", onKey);

    const resize = () => {
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    let lastReported = -1;
    const animate = () => {
      const elapsed = clock.getElapsedTime();
      active += (target - active) * (reduceMotion ? 1 : .075);
      const rounded = Math.round(active);
      if (rounded !== lastReported) { lastReported = rounded; onActiveChange(rounded); }
      panels.forEach((panel, index) => {
        const relative = index - active;
        const angle = relative * .43;
        const x = Math.sin(angle) * 7.15;
        const z = -Math.abs(relative) * .72 - Math.pow(Math.abs(relative), 1.34) * .28;
        const y = -.05 + Math.cos(angle * 1.3) * .08;
        panel.position.x += (x - panel.position.x) * .12;
        panel.position.y += (y - panel.position.y) * .12;
        panel.position.z += (z - panel.position.z) * .12;
        panel.rotation.y += ((-angle * .6) - panel.rotation.y) * .12;
        panel.rotation.x += ((pointerY * .018) - panel.rotation.x) * .08;
        const scale = Math.max(.72, 1 - Math.abs(relative) * .09);
        panel.scale.setScalar(scale);
        (panel.material as THREE.MeshBasicMaterial).opacity = Math.max(.14, 1 - Math.abs(relative) * .2);
        panel.renderOrder = 100 - Math.round(Math.abs(relative) * 10);
      });
      const activeAccent = new THREE.Color(modules[rounded]?.accent ?? "#58f5c7");
      const activeSecondary = new THREE.Color(modules[rounded]?.accentSecondary ?? "#b783ff");
      faceMaterial.color.lerp(activeSecondary, .035);
      featureMaterial.color.lerp(activeAccent, .045);
      const voiceEnergy = modeRef.current === "listening" || modeRef.current === "speaking" ? .12 : 0;
      face.rotation.y += ((pointerX * .16 + Math.sin(elapsed * .3) * .04) - face.rotation.y) * .035;
      face.rotation.x += ((-pointerY * .04) - face.rotation.x) * .035;
      face.scale.setScalar(1.25 + Math.sin(elapsed * 4.5) * voiceEnergy * .04);
      featureMaterial.size = .018 + voiceEnergy * (Math.sin(elapsed * 9) + 1) * .006;
      grid.position.z = -4 + (active % 1) * .12;
      camera.position.x += ((pointerX * .15) - camera.position.x) * .025;
      camera.position.y += ((.1 - pointerY * .06) - camera.position.y) * .025;
      camera.lookAt(0, -.08, -1.2);
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrame);
      observer.disconnect();
      container.removeEventListener("wheel", onWheel);
      container.removeEventListener("pointerdown", onPointerDown);
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("keydown", onKey);
      panelGeometry.dispose();
      textures.forEach((texture) => texture.dispose());
      panels.forEach((panel) => (panel.material as THREE.Material).dispose());
      faceGeometry.silhouette.dispose();
      faceGeometry.features.dispose();
      faceMaterial.dispose();
      featureMaterial.dispose();
      (grid.geometry as THREE.BufferGeometry).dispose();
      (grid.material as THREE.Material).dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [modules, onActiveChange, onOpen]);

  return <div className="spatial-scene" ref={host} aria-label="Interactive three-dimensional ORBIT command surfaces" />;
}
