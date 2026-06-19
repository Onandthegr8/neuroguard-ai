import {
  RISK_TIER_COLORS,
  RISK_TIER_BG,
  RISK_TIER_LABEL,
  scoreToTier,
  formatScore,
} from "../risk";

describe("risk utilities", () => {
  describe("scoreToTier", () => {
    it("returns very_low for scores 0–0.14", () => {
      expect(scoreToTier(0.0)).toBe("very_low");
      expect(scoreToTier(0.10)).toBe("very_low");
      expect(scoreToTier(0.14)).toBe("very_low");
    });

    it("returns low for scores 0.15–0.29", () => {
      expect(scoreToTier(0.15)).toBe("low");
      expect(scoreToTier(0.22)).toBe("low");
      expect(scoreToTier(0.29)).toBe("low");
    });

    it("returns moderate for scores 0.30–0.54", () => {
      expect(scoreToTier(0.30)).toBe("moderate");
      expect(scoreToTier(0.45)).toBe("moderate");
      expect(scoreToTier(0.54)).toBe("moderate");
    });

    it("returns high for scores 0.55–0.74", () => {
      expect(scoreToTier(0.55)).toBe("high");
      expect(scoreToTier(0.65)).toBe("high");
      expect(scoreToTier(0.74)).toBe("high");
    });

    it("returns very_high for scores 0.75–1.0", () => {
      expect(scoreToTier(0.75)).toBe("very_high");
      expect(scoreToTier(0.90)).toBe("very_high");
      expect(scoreToTier(1.0)).toBe("very_high");
    });
  });

  describe("formatScore", () => {
    it("formats 0.28 as '28.0%'", () => {
      expect(formatScore(0.28)).toBe("28.0%");
    });

    it("formats 0.0 as '0.0%'", () => {
      expect(formatScore(0.0)).toBe("0.0%");
    });

    it("formats 1.0 as '100.0%'", () => {
      expect(formatScore(1.0)).toBe("100.0%");
    });
  });

  describe("RISK_TIER_COLORS", () => {
    it("has a hex color entry for each risk tier", () => {
      const tiers: string[] = ["very_low", "low", "moderate", "high", "very_high"];
      tiers.forEach((tier) => {
        const color = RISK_TIER_COLORS[tier as keyof typeof RISK_TIER_COLORS];
        expect(color).toBeDefined();
        expect(color).toMatch(/^#[0-9A-Fa-f]{6}$/);
      });
    });
  });

  describe("RISK_TIER_BG", () => {
    it("has a Tailwind class string for each risk tier", () => {
      const tiers: string[] = ["very_low", "low", "moderate", "high", "very_high"];
      tiers.forEach((tier) => {
        const cls = RISK_TIER_BG[tier as keyof typeof RISK_TIER_BG];
        expect(cls).toBeDefined();
        expect(typeof cls).toBe("string");
        expect(cls.length).toBeGreaterThan(0);
      });
    });
  });

  describe("RISK_TIER_LABEL", () => {
    it("returns human-readable labels for all tiers", () => {
      expect(RISK_TIER_LABEL["very_low"]).toMatch(/very low/i);
      expect(RISK_TIER_LABEL["low"]).toMatch(/low/i);
      expect(RISK_TIER_LABEL["moderate"]).toMatch(/moderate/i);
      expect(RISK_TIER_LABEL["high"]).toMatch(/high/i);
      expect(RISK_TIER_LABEL["very_high"]).toMatch(/very high/i);
    });
  });
});
