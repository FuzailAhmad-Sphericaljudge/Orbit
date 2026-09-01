import { useEffect, useRef } from "react";
import * as THREE from "three";

export type CommanderMode = "idle" | "listening" | "speaking" | "alert";

type Props = { mode: CommanderMode };

function seededRandom(seed = 417) {
  let state = seed >>> 0;
  return () => ((state = (state * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function pointGeometry(points: number[][]) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points.flat(), 3));
  return geometry;
}

export function buildCommanderGeometry() {
  const random = seededRandom();
  const silhouette: number[][] = [];
  const features: number[][] = [];

  for (let index = 0; index < 5200; index += 1) {
    const phi = Math.acos(1 - 2 * random());
    const theta = Math.PI * 2 * random();
    const jaw = 0.7 + 0.28 * Math.max(0, Math.cos(phi));
    const x = Math.sin(phi) * Math.cos(theta) * 0.72 * jaw;
    const y = Math.cos(phi) * 1.02 + 0.18;
    const z = Math.sin(phi) * Math.sin(theta) * 0.66;
    silhouette.push([x, y, z]);
  }

  for (let index = 0; index < 700; index += 1) {
    const y = -0.82 - random() * 0.78;
    const width = 0.25 + (Math.abs(y + 0.82) / 0.78) * 0.14;
    const angle = Math.PI * 2 * random();
    silhouette.push([Math.cos(angle) * width, y, Math.sin(angle) * 0.32]);
  }

  for (let index = 0; index < 2200; index += 1) {
    const x = (random() - 0.5) * 3.8;
    const normalized = Math.abs(x) / 1.9;
    const y = -1.48 - Math.pow(normalized, 1.6) * 0.52 + (random() - 0.5) * 0.07;
    const z = (random() - 0.5) * (0.7 - normalized * 0.25);
    silhouette.push([x, y, z]);
  }

  for (const side of [-1, 1]) {
    for (let index = 0; index < 150; index += 1) {
      const t = random();
      features.push([side * (0.17 + t * 0.27), 0.31 + Math.sin(t * Math.PI) * 0.035, 0.61 + random() * 0.035]);
    }
  }
  for (let index = 0; index < 140; index += 1) {
    const t = index / 139;
    features.push([(t - 0.5) * 0.42, -0.28 - Math.sin(t * Math.PI) * 0.065, 0.64]);
  }
  for (let index = 0; index < 90; index += 1) {
    const t = index / 89;
    features.push([(random() - 0.5) * 0.08, 0.22 - t * 0.42, 0.69 + Math.sin(t * Math.PI) * 0.08]);
  }
  return { silhouette: pointGeometry(silhouette), features: pointGeometry(features) };
}

export function CommanderAvatar({ mode }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    const container = host.current;
    if (!container) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020711, 0.12);
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    camera.position.set(0, -0.08, 5.8);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    container.appendChild(renderer.domElement);

    const geometries = buildCommanderGeometry();
    const bodyMaterial = new THREE.PointsMaterial({ color: 0x61d9ff, size: 0.018, transparent: true, opacity: 0.58, blending: THREE.AdditiveBlending, depthWrite: false });
    const featureMaterial = new THREE.PointsMaterial({ color: 0xd9f7ff, size: 0.026, transparent: true, opacity: 0.96, blending: THREE.AdditiveBlending, depthWrite: false });
    const body = new THREE.Points(geometries.silhouette, bodyMaterial);
    const features = new THREE.Points(geometries.features, featureMaterial);
    const commander = new THREE.Group();
    commander.add(body, features);
    scene.add(commander);

    const ambientGeometry = new THREE.BufferGeometry();
    const ambient: number[] = [];
    const random = seededRandom(912);
    for (let index = 0; index < 1300; index += 1) {
      const radius = 2.1 + random() * 2.2;
      const angle = random() * Math.PI * 2;
      ambient.push(Math.cos(angle) * radius, (random() - 0.5) * 4.5, Math.sin(angle) * radius - 0.8);
    }
    ambientGeometry.setAttribute("position", new THREE.Float32BufferAttribute(ambient, 3));
    const fieldMaterial = new THREE.PointsMaterial({ color: 0x497cff, size: 0.012, transparent: true, opacity: 0.34, blending: THREE.AdditiveBlending, depthWrite: false });
    const field = new THREE.Points(ambientGeometry, fieldMaterial);
    scene.add(field);

    const cyan = new THREE.Color(0x61d9ff);
    const alert = new THREE.Color(0xff8d4c);
    const clock = new THREE.Clock();
    let frame = 0;
    let smoothedIntensity = 0;
    let pointerX = 0;
    let pointerY = 0;

    const trackPointer = (event: PointerEvent) => {
      pointerX = (event.clientX / window.innerWidth - 0.5) * 2;
      pointerY = (event.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("pointermove", trackPointer, { passive: true });

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

    const animate = () => {
      const elapsed = clock.getElapsedTime();
      const current = modeRef.current;
      const target = current === "speaking" ? 1 : current === "listening" ? 0.55 : current === "alert" ? 0.78 : 0.2;
      smoothedIntensity += (target - smoothedIntensity) * 0.045;
      const motion = reduceMotion ? 0 : 1;
      commander.rotation.y += ((Math.sin(elapsed * 0.28) * 0.045 + pointerX * 0.13) * motion - commander.rotation.y) * 0.035;
      commander.rotation.x += ((Math.sin(elapsed * 0.19) * 0.012 - pointerY * 0.045) * motion - commander.rotation.x) * 0.035;
      commander.position.y = Math.sin(elapsed * 0.8) * 0.025 * motion;
      field.rotation.y += 0.00035 * motion;
      const speakingPulse = current === "speaking" ? (Math.sin(elapsed * 10) + 1) * 0.5 : 0;
      features.scale.setScalar(1 + speakingPulse * 0.025 * motion);
      featureMaterial.size = 0.026 + smoothedIntensity * 0.012 + speakingPulse * 0.012;
      bodyMaterial.size = 0.018 + smoothedIntensity * 0.005;
      bodyMaterial.color.copy(cyan).lerp(alert, current === "alert" ? 0.8 : 0);
      featureMaterial.color.copy(new THREE.Color(0xd9f7ff)).lerp(alert, current === "alert" ? 0.65 : 0);
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("pointermove", trackPointer);
      geometries.silhouette.dispose();
      geometries.features.dispose();
      ambientGeometry.dispose();
      bodyMaterial.dispose();
      featureMaterial.dispose();
      fieldMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div className="commander-avatar" ref={host} aria-hidden="true" />;
}
