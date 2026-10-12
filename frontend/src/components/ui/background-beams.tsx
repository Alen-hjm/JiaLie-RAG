// Adapted from Aceternity UI Background Beams (Manu Arora).
// https://ui.aceternity.com/components/background-beams
// Original cubic paths and animated SVG gradients, reduced to 18 deterministic beams.
import { memo, useEffect, useId, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "motion/react";

export const BackgroundBeams = memo(function BackgroundBeams({
  paused = false,
}: {
  paused?: boolean;
}) {
  const id = useId(),
    reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null),
    inView = useInView(ref),
    [visible, setVisible] = useState(!document.hidden);
  useEffect(() => {
    const change = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", change);
    return () => document.removeEventListener("visibilitychange", change);
  }, []);
  const paths = Array.from({ length: 18 }, (_, i) => {
    const n = i * 2;
    return `M${-380 + n * 7} ${-189 - n * 8}C${-380 + n * 7} ${-189 - n * 8} ${-312 + n * 7} ${216 - n * 8} ${152 + n * 7} ${343 - n * 8}C${616 + n * 7} ${470 - n * 8} ${684 + n * 7} ${875 - n * 8} ${684 + n * 7} ${875 - n * 8}`;
  });
  const still = reduced || paused || !inView || !visible;
  return (
    <div ref={ref} className="background-beams" aria-hidden="true">
      <svg
        viewBox="0 0 696 316"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
      >
        {paths.map((path, i) => (
          <g key={i}>
            <path
              d={path}
              stroke="#b6aaa3"
              strokeOpacity=".12"
              strokeWidth=".6"
            />
            <path
              d={path}
              stroke={`url(#${id}-${i})`}
              strokeWidth="1"
              strokeOpacity=".65"
            />
          </g>
        ))}
        <defs>
          {paths.map((_, i) => (
            <motion.linearGradient
              key={i}
              id={`${id}-${i}`}
              initial={{ x1: "0%", x2: "25%", y1: "0%", y2: "25%" }}
              animate={
                still
                  ? { x1: "20%", x2: "75%", y1: "20%", y2: "75%" }
                  : {
                      x1: ["0%", "100%"],
                      x2: ["10%", "115%"],
                      y1: ["0%", "100%"],
                      y2: ["15%", "120%"],
                    }
              }
              transition={{
                duration: still ? 0 : 9 + (i % 5),
                ease: "easeInOut",
                repeat: still ? 0 : Infinity,
                delay: still ? 0 : i * 0.31,
              }}
            >
              <stop stopColor="#a399e3" stopOpacity="0" />
              <stop offset=".35" stopColor="#b2a4fb" />
              <stop offset=".6" stopColor="#e3b797" />
              <stop offset="1" stopColor="#e3b797" stopOpacity="0" />
            </motion.linearGradient>
          ))}
        </defs>
      </svg>
    </div>
  );
});
