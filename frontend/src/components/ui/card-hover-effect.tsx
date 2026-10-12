// Adapted from Aceternity UI Card Hover Effect (Manu Arora).
// https://ui.aceternity.com/components/card-hover-effect
// Native buttons, focus interaction and reduced motion suit this workspace.
import { ReactNode, useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { GlowingEffect } from "./glowing-effect";

export function HoverEffect({
  items,
  onSelect,
}: {
  items: { title: string; description: string; icon: ReactNode; tag: string }[];
  onSelect: (index: number) => void;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const id = useId(),
    reduced = useReducedMotion();
  return (
    <div className="hover-card-grid">
      {items.map((item, index) => (
        <motion.button
          whileHover={reduced ? undefined : { y: -5 }}
          whileTap={reduced ? undefined : { scale: 0.985 }}
          transition={{ type: "spring", stiffness: 320, damping: 24 }}
          type="button"
          className="hover-card-wrap"
          key={item.title}
          onClick={() => onSelect(index)}
          onMouseEnter={() => setHovered(index)}
          onMouseLeave={() => setHovered(null)}
          onFocus={() => setHovered(index)}
          onBlur={() => setHovered(null)}
        >
          <AnimatePresence>
            {hovered === index && (
              <motion.span
                className="hover-card-highlight"
                layoutId={reduced ? undefined : id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.18 }}
              />
            )}
          </AnimatePresence>
          <span className="hover-card">
            <GlowingEffect />
            <span className="scenario-top">
              <span className={`scenario-icon tone-${index}`}>{item.icon}</span>
              <span className="scenario-tag">{item.tag}</span>
            </span>
            <strong>
              {item.title}
              <span className="scenario-arrow">↗</span>
            </strong>
            <span className="scenario-description">{item.description}</span>
          </span>
        </motion.button>
      ))}
    </div>
  );
}
