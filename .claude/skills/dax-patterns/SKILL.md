---
name: dax-patterns
description: >
  Common DAX measure patterns. Use when generating, reviewing,
  or documenting DAX code for Power BI.
---

# DAX Pattern Library

## Naming: "Total ", "Avg ", "% ", "YTD ", "MTD " prefix, PascalCase with spaces

## Patterns

YTD with Fiscal Year:
  YTD Sales = VAR _Result = CALCULATE([Total Sales], DATESYTD(DimDate[Date], "6/30")) RETURN _Result

Previous Period:
  Sales vs PY = VAR _Cur = [Total Sales] VAR _PY = CALCULATE([Total Sales], SAMEPERIODLASTYEAR(DimDate[Date])) RETURN DIVIDE(_Cur - _PY, _PY)

Safe DIVIDE: NEVER [A]/[B], ALWAYS DIVIDE([A], [B], 0)

## Anti-patterns
- CALCULATE without filter modification
- Circular dependencies
- FORMAT() in measures
- Nested CALCULATE without VAR
