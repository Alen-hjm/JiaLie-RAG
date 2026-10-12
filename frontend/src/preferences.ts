import { useEffect, useState } from "react";

export type Preferences = {
  sendShortcut: "enter" | "modifier";
  resultsPerPage: 5 | 10;
  expandEvidence: boolean;
};

export const defaultPreferences: Preferences = {
  sendShortcut: "enter",
  resultsPerPage: 5,
  expandEvidence: false,
};
const key = "jialie.preferences.v1";
const eventName = "jialie-preferences-changed";

export function readPreferences(): Preferences {
  try {
    const data = JSON.parse(localStorage.getItem(key) || "{}");
    return {
      sendShortcut: data?.sendShortcut === "modifier" ? "modifier" : "enter",
      resultsPerPage: data?.resultsPerPage === 10 ? 10 : 5,
      expandEvidence: data?.expandEvidence === true,
    };
  } catch {
    return { ...defaultPreferences };
  }
}

export function savePreferences(value: Preferences) {
  localStorage.setItem(key, JSON.stringify(value));
  window.dispatchEvent(new Event(eventName));
}

export function usePreferences() {
  const [preferences, setPreferences] = useState(readPreferences);
  useEffect(() => {
    const update = () => setPreferences(readPreferences());
    window.addEventListener(eventName, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(eventName, update);
      window.removeEventListener("storage", update);
    };
  }, []);
  return preferences;
}
