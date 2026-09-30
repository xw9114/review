import type { SVGProps } from "react";

const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  library: "M4 4v16 M9 4v16 M14 4v16 M18 5l3 14 M3 20h18",
  layers: "m12 3 10 5-10 5L2 8z M2 12l10 5 10-5 M2 16l10 5 10-5",
  leaf: "M20 3c-7-1-15 3-15 9a6 6 0 0 0 6 6c6 0 9-8 9-15Z M4 21l11-12 M9 16v-5 M9 16h5",
  "arrow-up-right": "M6 18 18 6 M6 6h12v12",
  "arrow-right": "M4 12h16 M14 6l6 6-6 6",
  plus: "M12 5v14 M5 12h14",
  search: "M20 20l-5-5 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  "chevron-right": "m9 5 7 7-7 7",
  "chevron-down": "m5 9 7 7 7-7",
  moon: "M20 14.2A8.5 8.5 0 0 1 9.8 4 8.5 8.5 0 1 0 20 14.2Z",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5 19 19 M19 5l-1.5 1.5 M6.5 17.5 5 19",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12 M6 18 18 6",
  clock: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l3 2",
  chart: "M4 4v16h16 M8 15l4-5 4 2 4-6",
  book: "M12 5v16 M12 5C8 2 5 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-3-1-6-2-10 1Z",
  command: "M9 9H6a3 3 0 1 1 3-3v12a3 3 0 1 1-3-3h12a3 3 0 1 1-3 3V6a3 3 0 1 1 3 3H9Z",
  refresh: "M20 7v5h-5 M4 17v-5h5 M19 8a8 8 0 0 0-14-2 M5 16a8 8 0 0 0 14 2",
  edit: "m15 4 5 5 M4 15l-1 6 6-1L21 8a2 2 0 0 0 0-3l-2-2a2 2 0 0 0-3 0Z",
  trash: "M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7",
  folder: "M3 7V4h6l2 3h10v13H3Z",
  inbox: "M4 4h16v16H4z M4 14h5l2 3h2l2-3h5",
  rss: "M5 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4 M4 10a10 10 0 0 1 10 10 M4 4a16 16 0 0 1 16 16",
  link: "M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1 M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1",
  draft: "M5 3h10l4 4v14H5z M15 3v5h5 M8 12h8 M8 16h6",
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 20, ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d={paths[name]} />
    </svg>
  );
}
