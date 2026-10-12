// Aceternity Text Generate Effect, adapted for Chinese phrases and reduced motion.
// https://ui.aceternity.com/components/text-generate-effect
import { motion, useReducedMotion } from "motion/react";
export function TextGenerateEffect({ phrases }: { phrases: string[] }) {
  const reduced = useReducedMotion();
  return (
    <span className="text-generate" aria-label={phrases.join("")}>
      {phrases.map((phrase, index) => (
        <motion.span
          aria-hidden="true"
          key={phrase}
          initial={
            reduced ? false : { opacity: 0, filter: "blur(12px)", y: 20 }
          }
          animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
          transition={{
            duration: 0.85,
            delay: index * 0.17,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          {phrase}
        </motion.span>
      ))}
    </span>
  );
}
