# Interface Specification: CSV Core Types

## AC-01: Table Type
A `Table` dataclass must expose:
- `columns: list[str]` — ordered column names
- `rows: list[Row]` — ordered rows

## AC-02: Row Type
A `Row` dataclass must expose:
- `values: dict[str, CellValue]` — mapping of column name to cell value

## AC-03: CellValue Union
`CellValue` must be a union type accepting `str | int | float | None`.

## AC-04: ColumnSchema Type
A `ColumnSchema` dataclass must expose:
- `name: str`
- `dtype: str` — one of `"string"`, `"integer"`, `"float"`, `"null"`

## AC-05: TableSchema Type
A `TableSchema` dataclass must expose:
- `columns: list[ColumnSchema]`

## AC-06: Infer Schema
A function `infer_schema(table: Table) -> TableSchema` must return a schema inferred from the table's data. The dtype for each column is determined by the first non-None value. Columns with all-None values default to `"null"`.

## AC-07: Validate Row
A function `validate_row(schema: TableSchema, row: Row) -> list[str]` must return a list of validation error messages. An empty list means valid. Validation checks that each column in the schema exists in the row and that the value type matches the declared dtype (with implicit int-to-float promotion allowed for `"float"` columns).
