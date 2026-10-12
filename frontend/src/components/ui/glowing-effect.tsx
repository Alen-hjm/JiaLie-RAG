// Adapted from Aceternity Glowing Effect: angular pointer tracking + masked conic glow.
// https://ui.aceternity.com/components/glowing-effect
import { useEffect, useRef } from "react";
import { animate, useReducedMotion } from "motion/react";
export function GlowingEffect() {
  const ref = useRef<HTMLSpanElement>(null),
    reduced = useReducedMotion();
  useEffect(() => {
    const el = ref.current,
      parent = el?.parentElement;
    if (!el || !parent || reduced || !matchMedia("(pointer:fine)").matches)
      return;
    let frame = 0,
      angle = 0,
      animation: ReturnType<typeof animate> | undefined;
    const move = (event: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = parent.getBoundingClientRect();
        const target =
          (Math.atan2(
            event.clientY - box.top - box.height / 2,
            event.clientX - box.left - box.width / 2,
          ) *
            180) /
            Math.PI +
          90;
        const next = angle + ((target - angle + 540) % 360) - 180;
        animation?.stop();
        el.style.setProperty("--glow-active", "1");
        animation = animate(angle, next, {
          duration: 0.65,
          ease: [0.16, 1, 0.3, 1],
          onUpdate: (value) => {
            angle = value;
            el.style.setProperty("--glow-angle", `${value}deg`);
          },
        });
      });
    };
    const leave = () => el.style.setProperty("--glow-active", "0");
    parent.addEventListener("pointerenter", move);
    parent.addEventListener("pointermove", move);
    parent.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(frame);
      animation?.stop();
      parent.removeEventListener("pointerenter", move);
      parent.removeEventListener("pointermove", move);
      parent.removeEventListener("pointerleave", leave);
    };
  }, [reduced]);
  return <span ref={ref} className="aceternity-glow" aria-hidden="true" />;
}
