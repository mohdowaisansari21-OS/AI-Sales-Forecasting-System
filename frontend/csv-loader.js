/**
 * CsvLoader - generic, global CSV reader + column auto-detector.
 *
 * Works with ANY csv file, regardless of column names. Instead of matching
 * fixed header strings like "Date" or "Sales", it samples the actual cell
 * values in every column and scores each column by how well it behaves
 * like a date, a number, or a text label. This means it works the same
 * whether the file calls it "Date", "Order Date", "purchase_dt", etc.
 *
 * Usage:
 *   const result = CsvLoader.load(csvText);
 *   // result.headers      -> raw column names found in the file
 *   // result.rawRows      -> array of {header: rawStringValue}
 *   // result.mapping      -> { date, value, product, region } column names chosen
 *   // result.rows         -> normalized [{ Date, Sales, Product, Region }]
 *   // result.report()     -> human-readable string describing what was detected
 */
(function (global) {
  "use strict";

  function splitCsvLine(line) {
    const values = [];
    let current = "";
    let quoted = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === "\"") {
        if (quoted && line[i + 1] === "\"") {
          current += "\"";
          i++;
        } else {
          quoted = !quoted;
        }
      } else if (char === "," && !quoted) {
        values.push(current);
        current = "";
      } else {
        current += char;
      }
    }
    values.push(current);
    return values;
  }

  function parseCsv(text) {
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter((l) => l.trim().length > 0);
    if (!lines.length) return { headers: [], rows: [] };

    const headers = splitCsvLine(lines[0]).map((h) => h.trim());
    const rows = [];

    for (let i = 1; i < lines.length; i++) {
      const values = splitCsvLine(lines[i]);
      const row = {};
      headers.forEach((header, index) => {
        row[header] = values[index] !== undefined ? values[index].trim() : "";
      });
      rows.push(row);
    }

    return { headers, rows };
  }

  function looksLikeDate(value) {
    if (!value) return false;
    const trimmed = String(value).trim();
    if (!trimmed) return false;
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) return false;
    const parsed = new Date(trimmed);
    return !Number.isNaN(parsed.getTime());
  }

  function looksLikeNumber(value) {
    if (value === null || value === undefined) return false;
    const trimmed = String(value).trim();
    if (!trimmed) return false;
    const cleaned = trimmed.replace(/[$,\u20B9\u20AC\u00A3\s]/g, "");
    if (!cleaned) return false;
    return /^-?\d+(\.\d+)?$/.test(cleaned);
  }

  function toNumber(value) {
    const cleaned = String(value).trim().replace(/[$,\u20B9\u20AC\u00A3\s]/g, "");
    return Number(cleaned);
  }

  function sampleColumn(rows, header, sampleSize) {
    const values = [];
    for (let i = 0; i < rows.length && values.length < sampleSize; i++) {
      const v = rows[i][header];
      if (v !== undefined && v !== "") values.push(v);
    }
    return values;
  }

  function scoreColumns(headers, rows) {
    const sampleSize = Math.min(50, rows.length) || 1;

    return headers.map((header) => {
      const values = sampleColumn(rows, header, sampleSize);
      const n = values.length || 1;

      const dateHits = values.filter(looksLikeDate).length;
      const numberHits = values.filter(looksLikeNumber).length;

      const uniqueValues = new Set(values).size;
      const isMostlyUnique = uniqueValues / n > 0.9;

      return {
        header,
        dateScore: dateHits / n,
        numberScore: numberHits / n,
        uniqueRatio: uniqueValues / n,
        sampleCount: n,
        isMostlyUnique,
      };
    });
  }

  const DATE_KEYWORDS = ["date", "day", "period", "time"];
  const VALUE_KEYWORDS = ["sales", "revenue", "amount", "total", "price", "value", "income", "earning"];
  const AVOID_VALUE_KEYWORDS = ["id", "code", "zip", "postal", "phone", "quantity", "qty", "discount", "rank", "index"];
  const PRODUCT_KEYWORDS = ["product", "category", "item", "name", "sku"];
  const REGION_KEYWORDS = ["region", "state", "city", "market", "location", "area", "country", "branch"];

  function headerMatches(header, keywords) {
    const lower = header.toLowerCase();
    return keywords.some((kw) => lower.includes(kw));
  }

  function pickDateColumn(scored) {
    const candidates = scored.filter((c) => c.dateScore >= 0.7);
    if (!candidates.length) return null;

    candidates.sort((a, b) => {
      const aKeyword = headerMatches(a.header, DATE_KEYWORDS) ? 1 : 0;
      const bKeyword = headerMatches(b.header, DATE_KEYWORDS) ? 1 : 0;
      if (aKeyword !== bKeyword) return bKeyword - aKeyword;
      return b.dateScore - a.dateScore;
    });

    return candidates[0].header;
  }

  function pickValueColumn(scored, excludeHeader) {
    const numeric = scored.filter((c) => c.header !== excludeHeader && c.numberScore >= 0.85);
    if (!numeric.length) return null;

    // Tier 1: numeric columns whose header clearly means "this is the
    // money/quantity we care about" (e.g. "Sales", "Revenue") and isn't
    // an ID/quantity/discount-type field. Uniqueness doesn't disqualify
    // these - real sales figures are often mostly distinct values.
    const strongMatches = numeric.filter(
      (c) => headerMatches(c.header, VALUE_KEYWORDS) && !headerMatches(c.header, AVOID_VALUE_KEYWORDS)
    );
    if (strongMatches.length) {
      strongMatches.sort((a, b) => b.numberScore - a.numberScore);
      return strongMatches[0].header;
    }

    // Tier 2: no clear keyword match anywhere - prefer non-unique,
    // non-ID-like numeric columns (avoids picking Row ID / Postal Code).
    let candidates = numeric.filter(
      (c) => !c.isMostlyUnique && !headerMatches(c.header, AVOID_VALUE_KEYWORDS)
    );
    if (!candidates.length) {
      candidates = numeric.filter((c) => !headerMatches(c.header, AVOID_VALUE_KEYWORDS));
    }
    if (!candidates.length) {
      candidates = numeric;
    }

    candidates.sort((a, b) => b.numberScore - a.numberScore);
    return candidates[0].header;
  }

  function pickDimensionColumns(scored, dateHeader, valueHeader) {
    const remaining = scored.filter(
      (c) => c.header !== dateHeader && c.header !== valueHeader && c.numberScore < 0.85
    );

    const product = remaining.find((c) => headerMatches(c.header, PRODUCT_KEYWORDS));
    const region = remaining.find(
      (c) => headerMatches(c.header, REGION_KEYWORDS) && (!product || c.header !== product.header)
    );

    const leftovers = remaining.filter(
      (c) => (!product || c.header !== product.header) && (!region || c.header !== region.header)
    );

    return {
      product: (product && product.header) || (leftovers[0] && leftovers[0].header) || null,
      region: (region && region.header) || (leftovers[1] && leftovers[1].header) || null,
    };
  }

  function autoMapColumns(headers, rows) {
    const scored = scoreColumns(headers, rows);
    const dateHeader = pickDateColumn(scored);
    const valueHeader = pickValueColumn(scored, dateHeader);
    const dims = pickDimensionColumns(scored, dateHeader, valueHeader);

    return {
      date: dateHeader,
      value: valueHeader,
      product: dims.product,
      region: dims.region,
      scored,
    };
  }

  function normalizeWithMapping(rows, mapping) {
    if (!mapping.date || !mapping.value) return [];

    return rows
      .map((row) => {
        const rawDate = row[mapping.date];
        const rawValue = row[mapping.value];
        const date = looksLikeDate(rawDate) ? new Date(rawDate) : null;
        const value = looksLikeNumber(rawValue) ? toNumber(rawValue) : NaN;

        return {
          Date: date,
          Sales: value,
          Product: (mapping.product && row[mapping.product]) || "General",
          Region: (mapping.region && row[mapping.region]) || "All",
        };
      })
      .filter((row) => row.Date && Number.isFinite(row.Sales))
      .sort((a, b) => a.Date - b.Date);
  }

  function report(headers, mapping, normalizedCount, totalRows) {
    const lines = [];
    lines.push(`Columns found: ${headers.join(", ")}`);
    lines.push(`Detected date column: ${mapping.date || "(none found)"}`);
    lines.push(`Detected value/sales column: ${mapping.value || "(none found)"}`);
    lines.push(`Detected product/category column: ${mapping.product || "(none)"}`);
    lines.push(`Detected region column: ${mapping.region || "(none)"}`);
    lines.push(`Usable rows: ${normalizedCount} of ${totalRows}`);
    return lines.join("\n");
  }

  function load(text) {
    const { headers, rows } = parseCsv(text);
    const mapping = autoMapColumns(headers, rows);
    const normalized = normalizeWithMapping(rows, mapping);

    return {
      headers,
      rawRows: rows,
      mapping,
      rows: normalized,
      report: () => report(headers, mapping, normalized.length, rows.length),
    };
  }

  global.CsvLoader = {
    load,
    parseCsv,
    autoMapColumns,
    normalizeWithMapping,
    splitCsvLine,
    looksLikeDate,
    looksLikeNumber,
  };
})(typeof window !== "undefined" ? window : globalThis);
