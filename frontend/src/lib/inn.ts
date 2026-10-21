/** ИНН check digits by the ФНС algorithm: 10 digits for a company, 12 for an entrepreneur. */
const W10 = [2, 4, 10, 3, 5, 9, 4, 6, 8];
const W11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8];
const W12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8];

function digit(digits: number[], weights: number[]): number {
  return (weights.reduce((sum, weight, index) => sum + weight * (digits[index] ?? 0), 0) % 11) % 10;
}

export function innIsValid(inn: string): boolean {
  if (!/^\d{10}(\d{2})?$/.test(inn)) return false;
  const digits = [...inn].map(Number);
  if (digits.length === 10) return digits[9] === digit(digits, W10);
  return digits[10] === digit(digits, W11) && digits[11] === digit(digits, W12);
}
