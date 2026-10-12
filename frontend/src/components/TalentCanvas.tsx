// Aceternity 3D Card's pointer/perspective approach, adapted to an interactive workflow.
// https://ui.aceternity.com/components/3d-card-effect
import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowUpOutlined,
  FileSearchOutlined,
  CheckOutlined,
} from "@ant-design/icons";
import { GlowingEffect } from "./ui/glowing-effect";
export function TalentCanvas({
  onStart,
  onLibrary,
}: {
  onStart: () => void;
  onLibrary: () => void;
}) {
  const reduced = useReducedMotion(),
    [rotation, setRotation] = useState({ rotateX: 0, rotateY: 0 });
  return (
    <div
      className="talent-canvas"
      onPointerMove={(event) => {
        if (reduced || event.pointerType !== "mouse") return;
        const box = event.currentTarget.getBoundingClientRect();
        setRotation({
          rotateX: -(event.clientY - box.top - box.height / 2) / 45,
          rotateY: (event.clientX - box.left - box.width / 2) / 45,
        });
      }}
      onPointerLeave={() => setRotation({ rotateX: 0, rotateY: 0 })}
    >
      <motion.div
        className="canvas-depth"
        animate={rotation}
        transition={{ type: "spring", stiffness: 95, damping: 18 }}
      >
        <motion.div
          className="canvas-caption"
          initial={reduced ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.8 }}
        >
          BEYOND THE RESUME<span>从经历，到可能</span>
        </motion.div>
        <motion.button
          whileHover={reduced ? undefined : { y: -7, scale: 1.025 }}
          whileTap={reduced ? undefined : { scale: 0.98 }}
          className="canvas-sheet sheet-back"
          onClick={onStart}
          initial={reduced ? false : { opacity: 0, y: 50, rotate: -16 }}
          animate={{ opacity: 1, y: 0, rotate: -9 }}
          transition={{ delay: 0.2, duration: 1, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="sheet-number">01 / BRIEF</span>
          <strong>
            你寻找的，
            <br />
            不止一个关键词。
          </strong>
          <span className="sheet-tags">
            <i>专业能力</i>
            <i>行业经历</i>
            <i>团队经验</i>
          </span>
          <span className="sheet-action">
            描述理想人选 <ArrowUpOutlined />
          </span>
        </motion.button>
        <motion.button
          whileHover={reduced ? undefined : { y: -7, scale: 1.025 }}
          whileTap={reduced ? undefined : { scale: 0.98 }}
          className="canvas-sheet sheet-front"
          onClick={onLibrary}
          initial={reduced ? false : { opacity: 0, y: 80, rotate: 12 }}
          animate={{ opacity: 1, y: 0, rotate: 6 }}
          transition={{ delay: 0.45, duration: 1, ease: [0.16, 1, 0.3, 1] }}
        >
          <GlowingEffect />
          <span className="sheet-number">
            02 / EVIDENCE <FileSearchOutlined />
          </span>
          <strong>
            每一段经历，
            <br />
            <em>都有迹可循。</em>
          </strong>
          <span className="evidence-lines">
            <i />
            <i />
            <i />
          </span>
          <span className="sheet-verified">
            <CheckOutlined /> 回到简历，核实每个推荐
          </span>
        </motion.button>
        <div className="canvas-footnote">
          <span>需求 → 人才 → 依据</span>
          <span>JIALIE / TALENT STUDIO</span>
        </div>
      </motion.div>
    </div>
  );
}
