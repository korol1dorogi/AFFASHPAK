import { describe, expect, it } from "vitest";

import { innIsValid } from "./inn";

describe("innIsValid (ФНС check digits)", () => {
  it.each(["0001000028", "0001000081", "000100000170", "000100000318"])(
    "accepts registry INN %s",
    (inn) => expect(innIsValid(inn)).toBe(true),
  );

  it.each(["0012345678", "0001000029", "000100000171", "123", "00010000281", "abcdefghij"])(
    "rejects %s",
    (inn) => expect(innIsValid(inn)).toBe(false),
  );
});
