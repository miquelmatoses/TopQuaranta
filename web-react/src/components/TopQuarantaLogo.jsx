/**
 * TopQuarantaLogo — horizontal SVG wordmark + "redolí" mark.
 *
 * Uses `currentColor` throughout so a single asset renders black on
 * the yellow header, white on the black body, or any brand colour
 * the parent sets via `color:`.
 */
export default function TopQuarantaLogo({ className = 'h-8 w-auto' }) {
  return (
    <svg
      viewBox="0 0 280 64"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="TopQuaranta"
      className={className}
    >
      {/* Redolí — circle ring + play triangle + dot (same silhouette as
          the legacy favicon, condensed for horizontal layout). */}
      <g transform="translate(6 6) scale(0.104)" fill="currentColor">
        <path
          transform="translate(-190 -175)"
          d="M 698.16 338.87 C 718.10 441.45 651.02 540.79 548.32 560.75 C 499.01 570.34 447.91 559.96 406.27 531.91 C 364.63 503.85 335.86 460.42 326.28 411.15 C 306.34 308.57 373.42 209.23 476.12 189.27 C 525.43 179.68 576.53 190.05 618.17 218.11 C 659.81 246.17 688.58 289.60 698.16 338.87 Z M 675.08 369.32 C 673.58 326.20 654.99 285.45 623.40 256.03 C 591.82 226.61 549.82 210.93 506.66 212.44 C 416.78 215.58 346.46 290.90 349.60 380.68 C 351.11 423.80 369.70 464.55 401.28 493.97 C 432.87 523.38 474.86 539.06 518.02 537.56 C 607.90 534.42 678.22 459.09 675.08 369.32 Z"
        />
        <path
          transform="translate(-200 -173)"
          d="m 600.61,387.84 -140.32,80.42 c -5.04,2.89 -11.23,2.87 -16.25,-0.04 c -5.02,-2.91 -8.11,-8.28 -8.11,-14.08 l 0.05,-161.74 c 0.00,-5.82 3.11,-11.19 8.15,-14.09 c 5.04,-2.90 11.25,-2.89 16.28,0.02 l 140.27,81.31 c 5.04,2.92 8.13,8.30 8.12,14.12 c -0.01,5.82 -3.14,11.19 -8.19,14.08 z m -137.52,47.53 c 0,0.14 0.07,0.28 0.20,0.35 c 0.12,0.07 0.28,0.07 0.40,0.00 l 107.19,-61.64 c 0.12,-0.07 0.20,-0.20 0.20,-0.35 c 0,-0.14 -0.08,-0.27 -0.20,-0.35 L 463.91,311.38 c -0.12,-0.08 -0.28,-0.08 -0.40,-0.01 c -0.13,0.07 -0.21,0.20 -0.21,0.35 z"
        />
        <circle cx="275" cy="313" r="21" />
      </g>

      <text
        x="72"
        y="42"
        fontFamily="'Playfair Display', Georgia, serif"
        fontSize="28"
        fontWeight="700"
        fill="currentColor"
        letterSpacing="0.005em"
      >
        TopQuaranta
      </text>
    </svg>
  )
}
