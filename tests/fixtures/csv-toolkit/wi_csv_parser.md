# Interface Specification: CSV Parser

## Dependencies
- `interface_ref`: `csv_types`

## AC-01: Parse String
A function `parse_csv(text: str, delimiter: str = ",") -> Table` must parse a CSV-formatted string and return a `Table`. The first row is treated as column headers.

## AC-02: Quoted Fields
The parser must handle double-quoted fields containing the delimiter character, newlines, and escaped quotes (`""` → `"`).

## AC-03: Type Inference
Numeric values (integers and floats) must be converted to their native Python types. Non-numeric values remain as strings. Empty fields become `None`.

## AC-04: Delimiter Detection
A function `detect_delimiter(text: str) -> str` must return the most likely delimiter from `(",", ";", "\t", "|")` based on consistent column counts across the first 5 non-empty lines.

## AC-05: Auto-Parse
A function `auto_parse(text: str) -> Table` must detect the delimiter using `detect_delimiter` and then parse the table.

## AC-06: Malformed Input
If the input has inconsistent column counts across rows, `parse_csv` must raise `ParseError` with `message: str` and `line_number: int`.
