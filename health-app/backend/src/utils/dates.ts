export function dateOnly(value: string | Date) {
  const date = typeof value === "string" ? new Date(`${value}T00:00:00.000Z`) : value;
  if (Number.isNaN(date.getTime())) {
    throw new Error("Invalid date");
  }
  return date;
}

export function formatDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

export function addDays(value: Date, days: number) {
  const result = new Date(value);
  result.setUTCDate(result.getUTCDate() + days);
  return result;
}

export function todayUtc() {
  return dateOnly(new Date().toISOString().slice(0, 10));
}
