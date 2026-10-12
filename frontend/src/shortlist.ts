import { useEffect, useState } from "react";

// Store only IDs; candidate details are always fetched from the authenticated API.
const storageKey = "jialie.shortlist.v1";
const changeEvent = "jialie-shortlist-changed";
export function readShortlist(): string[] {
  try {
    const data: unknown = JSON.parse(localStorage.getItem(storageKey) || "[]");
    return Array.isArray(data)
      ? [
          ...new Set(
            data.filter((item): item is string => typeof item === "string"),
          ),
        ]
      : [];
  } catch {
    return [];
  }
}
export function toggleShortlist(id: string) {
  const ids = readShortlist();
  const next = ids.includes(id)
    ? ids.filter((value) => value !== id)
    : [...ids, id];
  localStorage.setItem(storageKey, JSON.stringify(next));
  window.dispatchEvent(new Event(changeEvent));
}
export function useShortlist() {
  const [ids, setIds] = useState(readShortlist);
  useEffect(() => {
    const refresh = () => setIds(readShortlist());
    window.addEventListener(changeEvent, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(changeEvent, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  return ids;
}
