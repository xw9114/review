"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Icon } from "./icon";

function readTheme() {
  try { return window.localStorage.getItem("theme") === "dark" ? "dark" : "light"; }
  catch { return document.documentElement.dataset.theme === "dark" ? "dark" : "light"; }
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("themechange", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("themechange", callback);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "light");
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try { window.localStorage.setItem("theme", next); } catch { /* Keep the session theme if storage is unavailable. */ }
    window.dispatchEvent(new Event("themechange"));
  }

  return (
    <button type="button" className="icon-button theme-toggle" onClick={toggleTheme} aria-label={theme === "light" ? "切换到深色模式" : "切换到浅色模式"} title={theme === "light" ? "深色模式" : "浅色模式"}>
      <Icon name={theme === "light" ? "moon" : "sun"} size={19} />
    </button>
  );
}
