import type { Preferences } from "@/lib/types";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type Schedule = Pick<Preferences, "briefing_frequency" | "briefing_hour" | "briefing_weekday" | "timezone">;

/** Plain-language description of when the scheduler (app/ai/briefing.py `is_due`) generates a briefing. */
export function scheduleSummary(p: Schedule): string {
  if (p.briefing_frequency === "off") return "No scheduled briefing — generate one on demand from the Daily Briefing page.";
  const at = `${String(p.briefing_hour).padStart(2, "0")}:00 (${p.timezone})`;
  const when =
    p.briefing_frequency === "weekly"
      ? `every ${WEEKDAYS[p.briefing_weekday] ?? "Monday"} at ${at}`
      : p.briefing_frequency === "weekdays"
        ? `Monday to Friday at ${at}`
        : `every day at ${at}`;
  return `Generated ${when}. If the server was busy at that time, it is caught up later the same day — never twice.`;
}
