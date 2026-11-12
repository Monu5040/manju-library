/** Minutes in a day. Ranges are [start, end) minutes after midnight; an end past 1440 runs into the next day. */
export const MINUTES_PER_DAY = 1440

/** True when two daily time ranges overlap, including across midnight (as on the server). */
export function overlaps(a: [number, number], b: [number, number]): boolean {
  return [0, MINUTES_PER_DAY, -MINUTES_PER_DAY].some((shift) => a[0] < b[1] + shift && b[0] + shift < a[1])
}
