from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .correlation import CorrelationArtifacts, ranked_pairs
from .atomic_io import atomic_target
from .settings import DashboardConfig


HEADER_FILL = PatternFill(fill_type="solid", fgColor="10243E")
HEADER_FONT = Font(color="FFFFFF", bold=True)

# Text starting with one of these is evaluated as a formula by Excel and similar apps.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """Neutralise spreadsheet formula injection: prefix risky strings with an apostrophe.

    Only strings are touched; numbers (including negative correlations) pass through unchanged.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def safe_row(values) -> list:
    return [safe_cell(value) for value in values]


def safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy of ``frame`` with formula-like strings neutralised in object columns and headers."""
    result = frame.copy()
    for position in range(result.shape[1]):
        series = result.iloc[:, position]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            result.iloc[:, position] = series.map(safe_cell)
    result.columns = [safe_cell(column) for column in result.columns]
    return result


def export_workbook(
    artifacts: CorrelationArtifacts,
    config: DashboardConfig,
    destination: Path,
) -> None:
    workbook = Workbook()
    metadata_sheet = workbook.active
    metadata_sheet.title = "metadata"
    universe_sheet = workbook.create_sheet("universe")
    prices_sheet = workbook.create_sheet("prices")
    returns_sheet = workbook.create_sheet("returns")
    corr_sheet = workbook.create_sheet("correlation")
    pairs_sheet = workbook.create_sheet("pair_summary")

    _write_metadata_sheet(metadata_sheet, artifacts)
    universe_records = artifacts.metadata["universe"].get("final_universe", [])
    universe_frame = pd.DataFrame(universe_records)
    if universe_frame.empty:
        universe_frame = pd.DataFrame(
            {
                "rank": range(1, len(artifacts.metadata["tickers"]) + 1),
                "ticker": artifacts.metadata["tickers"],
            }
        )
    _write_frame(universe_sheet, universe_frame, index_label="row", include_index=False)
    _write_frame(prices_sheet, artifacts.prices, index_label="date")
    _write_frame(returns_sheet, artifacts.returns, index_label="date")
    _write_frame(corr_sheet, artifacts.correlation, index_label="ticker")
    _write_pairs_sheet(pairs_sheet, artifacts, config)

    row_count = len(artifacts.correlation.index) + 1
    col_count = len(artifacts.correlation.columns) + 1
    corr_sheet.conditional_formatting.add(
        f"B2:{get_column_letter(col_count)}{row_count}",
        ColorScaleRule(
            start_type="num",
            start_value=-1,
            start_color=config.visuals["heatmap_min_color"].replace("#", ""),
            mid_type="num",
            mid_value=0,
            mid_color=config.visuals["heatmap_mid_color"].replace("#", ""),
            end_type="num",
            end_value=1,
            end_color=config.visuals["heatmap_max_color"].replace("#", ""),
        ),
    )

    with atomic_target(destination) as tmp:
        workbook.save(tmp)


def _write_metadata_sheet(sheet, artifacts: CorrelationArtifacts) -> None:
    sheet.append(["field", "value"])
    _style_header(sheet)

    def append_mapping(prefix: str, payload: dict):
        for key, value in payload.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                append_mapping(full_key, value)
            else:
                sheet.append(safe_row([full_key, str(value)]))

    append_mapping("", artifacts.metadata)
    for column in ("A", "B"):
        sheet.column_dimensions[column].width = 42


def _write_pairs_sheet(sheet, artifacts: CorrelationArtifacts, config: DashboardConfig) -> None:
    limit = int(config.analytics["pair_table_limit"])
    strongest = ranked_pairs(artifacts.correlation, limit=limit, ascending=False)
    weakest = ranked_pairs(artifacts.correlation, limit=limit, ascending=True)

    sheet.append(["strongest_pairs", "correlation", "", "weakest_pairs", "correlation"])
    _style_header(sheet)
    for index in range(limit):
        strong = strongest[index] if index < len(strongest) else {"pair": "", "correlation": ""}
        weak = weakest[index] if index < len(weakest) else {"pair": "", "correlation": ""}
        sheet.append(
            safe_row(
                [
                    strong["pair"],
                    strong["correlation"],
                    "",
                    weak["pair"],
                    weak["correlation"],
                ]
            )
        )
    for column_index in range(1, 6):
        sheet.column_dimensions[get_column_letter(column_index)].width = 24


def _write_frame(sheet, frame, index_label: str, include_index: bool = True) -> None:
    header = [index_label, *list(frame.columns)] if include_index else list(frame.columns)
    sheet.append(safe_row(header))
    _style_header(sheet)

    if include_index:
        for index, row in frame.iterrows():
            values = [str(index.date()) if hasattr(index, "date") else str(index), *row.tolist()]
            sheet.append(safe_row(values))
    else:
        for _, row in frame.iterrows():
            sheet.append(safe_row(row.tolist()))

    for cell in sheet["A"]:
        cell.alignment = Alignment(horizontal="left")

    for column_index in range(1, len(header) + 1):
        sheet.column_dimensions[get_column_letter(column_index)].width = 18


def _style_header(sheet) -> None:
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
