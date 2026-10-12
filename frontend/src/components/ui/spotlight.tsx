// Adapted from Aceternity UI Spotlight: https://ui.aceternity.com/components/spotlight
import { useId } from "react";

export function Spotlight({ fill = "#90bda0" }: { fill?: string }) {
  const id = useId();
  return (
    <svg
      className="aceternity-spotlight"
      aria-hidden="true"
      viewBox="0 0 3787 2842"
      fill="none"
    >
      <g filter={`url(#${id})`}>
        <ellipse
          cx="1924.71"
          cy="273.501"
          rx="1924.71"
          ry="273.501"
          transform="matrix(-0.822377 -0.568943 -0.568943 0.822377 3631.88 2291.09)"
          fill={fill}
          fillOpacity=".21"
        />
      </g>
      <defs>
        <filter
          id={id}
          x=".860352"
          y=".838989"
          width="3785.16"
          height="2840.26"
          filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB"
        >
          <feFlood floodOpacity="0" result="BackgroundImageFix" />
          <feBlend
            mode="normal"
            in="SourceGraphic"
            in2="BackgroundImageFix"
            result="shape"
          />
          <feGaussianBlur stdDeviation="151" result="effect1_foregroundBlur" />
        </filter>
      </defs>
    </svg>
  );
}
