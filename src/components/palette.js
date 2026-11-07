// Categorical slots from the validated reference palette (adjacent-pair CVD safe).
// Order is fixed: colour follows the dwelling type, never its rank.
const LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"];
const DARK = ["#3987e5", "#d95926", "#199e70", "#c98500"];

export const DWELLING_TYPES = ["Single", "Semi-Detached", "Row", "Apartment"];

export function dwellingColor(dark) {
  return {domain: DWELLING_TYPES, range: dark ? DARK : LIGHT, legend: true};
}

export function seriesColor(dark, i = 0) {
  return (dark ? DARK : LIGHT)[i];
}
