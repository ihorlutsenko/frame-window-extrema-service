from __future__ import annotations

from dataclasses import dataclass
from math import floor, log2
from typing import Any


class AnalysisError(ValueError):
    """Raised for invalid input or impossible analysis settings."""


@dataclass(frozen=True)
class Sample:
    global_index: int
    local_index: int
    value: float


@dataclass(frozen=True)
class Extremum:
    ordinal: int
    global_index: int
    local_index: int
    value: float
    kind: str


@dataclass(frozen=True)
class Run:
    value: float
    sample: Sample


def _parse_number(token: str, line_number: int) -> float:
    normalized = token.strip()
    if not normalized:
        raise AnalysisError(f"Порожній рядок у вхідному файлі на рядку {line_number}.")

    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return float(normalized)
    except ValueError as exc:
        raise AnalysisError(
            f"Не вдалося прочитати число на рядку {line_number}: {token!r}"
        ) from exc


def _split_numeric_line(raw_line: str) -> list[str]:
    stripped = raw_line.strip()
    if not stripped:
        return []

    if ";" in stripped:
        return [token.strip() for token in stripped.split(";") if token.strip()]

    if "\t" in stripped:
        return [token.strip() for token in stripped.split("\t") if token.strip()]

    if "," in stripped:
        if stripped.count(",") == 1 and "." not in stripped and " " not in stripped:
            return [stripped]
        return [token.strip() for token in stripped.split(",") if token.strip()]

    if len(stripped.split()) > 1:
        return [token.strip() for token in stripped.split() if token.strip()]

    return [stripped]


def parse_input_text(text: str) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        tokens = _split_numeric_line(raw_line)
        for token in tokens:
            value = _parse_number(token, line_number)
            points.append((len(points) + 1, value))

    if not points:
        raise AnalysisError("Вхідний файл не містить жодного числа.")

    return points


def _as_positive_int(raw_value: str | None, field_name: str) -> int | None:
    if raw_value is None:
        return None

    stripped = raw_value.strip()
    if not stripped:
        return None

    try:
        value = int(stripped)
    except ValueError as exc:
        raise AnalysisError(f"Поле `{field_name}` має бути цілим числом.") from exc

    if value <= 0:
        raise AnalysisError(f"Поле `{field_name}` має бути додатним цілим числом.")

    return value


def _as_nonnegative_int(raw_value: str | None, field_name: str) -> int | None:
    if raw_value is None:
        return None

    stripped = raw_value.strip()
    if not stripped:
        return None

    try:
        value = int(stripped)
    except ValueError as exc:
        raise AnalysisError(f"Поле `{field_name}` має бути цілим числом.") from exc

    if value < 0:
        raise AnalysisError(f"Поле `{field_name}` не може бути від'ємним.")

    return value


def select_frame(
    source_points: list[tuple[int, float]],
    frame_size_raw: str | None,
    frame_number_raw: str | None,
    manual_start_raw: str | None,
    manual_end_raw: str | None,
) -> tuple[list[Sample], dict[str, Any]]:
    total_count = len(source_points)
    manual_start = _as_positive_int(manual_start_raw, "manual_start")
    manual_end = _as_positive_int(manual_end_raw, "manual_end")

    if manual_start is not None or manual_end is not None:
        if manual_start is None or manual_end is None:
            raise AnalysisError(
                "Для ручного режиму треба задати і початковий, і кінцевий номер спостереження."
            )
        if manual_end < manual_start:
            raise AnalysisError("Кінцевий номер спостереження не може бути меншим за початковий.")
        if manual_start > total_count or manual_end > total_count:
            raise AnalysisError("Ручний діапазон виходить за межі вхідного масиву.")

        selected = source_points[manual_start - 1 : manual_end]
        mode = {
            "type": "manual",
            "manualStart": manual_start,
            "manualEnd": manual_end,
            "frameSize": None,
            "frameNumber": None,
        }
    else:
        frame_size = _as_positive_int(frame_size_raw, "frame_size")
        frame_number = _as_positive_int(frame_number_raw, "frame_number")
        if frame_size is None or frame_number is None:
            raise AnalysisError(
                "Треба або задати ручний діапазон, або вказати розмір фрейму та номер фрейму."
            )

        start = (frame_number - 1) * frame_size + 1
        if start > total_count:
            raise AnalysisError("Номер фрейму виходить за межі вхідного масиву.")
        end = min(total_count, frame_number * frame_size)
        selected = source_points[start - 1 : end]
        mode = {
            "type": "fixed_frame",
            "manualStart": None,
            "manualEnd": None,
            "frameSize": frame_size,
            "frameNumber": frame_number,
        }

    frame_samples = [
        Sample(global_index=global_index, local_index=idx + 1, value=value)
        for idx, (global_index, value) in enumerate(selected)
    ]

    if not frame_samples:
        raise AnalysisError("Обраний фрейм порожній.")

    mode["selectedGlobalStart"] = frame_samples[0].global_index
    mode["selectedGlobalEnd"] = frame_samples[-1].global_index
    mode["selectedCount"] = len(frame_samples)
    return frame_samples, mode


def _build_runs(samples: list[Sample]) -> list[Run]:
    runs: list[Run] = []
    start = 0
    while start < len(samples):
        end = start + 1
        while end < len(samples) and samples[end].value == samples[start].value:
            end += 1

        run_length = end - start
        representative_offset = (run_length - 1) // 2
        runs.append(Run(value=samples[start].value, sample=samples[start + representative_offset]))
        start = end

    return runs


def extract_extrema(samples: list[Sample]) -> list[Extremum]:
    if len(samples) < 3:
        return []

    runs = _build_runs(samples)
    if len(runs) < 3:
        return []

    extrema: list[Extremum] = []
    ordinal = 1
    for idx in range(1, len(runs) - 1):
        prev_run = runs[idx - 1]
        current_run = runs[idx]
        next_run = runs[idx + 1]

        kind = None
        if current_run.value > prev_run.value and current_run.value > next_run.value:
            kind = "max"
        elif current_run.value < prev_run.value and current_run.value < next_run.value:
            kind = "min"

        if kind is None:
            continue

        extrema.append(
            Extremum(
                ordinal=ordinal,
                global_index=current_run.sample.global_index,
                local_index=current_run.sample.local_index,
                value=current_run.value,
                kind=kind,
            )
        )
        ordinal += 1

    return extrema


def _max_k_for_extrema(extrema_count: int) -> int:
    if extrema_count < 2:
        return -1
    return int(floor(log2(extrema_count - 1)))


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _event_rows_for_k(
    extrema: list[Extremum], step: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diff_rows: list[dict[str, Any]] = []
    for start_index in range(0, len(extrema) - step):
        current = extrema[start_index]
        shifted = extrema[start_index + step]
        signed_diff = shifted.value - current.value
        subseries_index = ((shifted.ordinal - 1) % step) + 1
        diff_rows.append(
            {
                "startOrdinal": current.ordinal,
                "startLocalIndex": current.local_index,
                "startGlobalIndex": current.global_index,
                "startAmplitude": current.value,
                "endOrdinal": shifted.ordinal,
                "endLocalIndex": shifted.local_index,
                "endGlobalIndex": shifted.global_index,
                "endAmplitude": shifted.value,
                "signedDiff": signed_diff,
                "absDiff": abs(signed_diff),
                "subseriesIndex": subseries_index,
            }
        )

    sign_changes: list[dict[str, Any]] = []
    sign_change_diff_rows: list[dict[str, Any]] = []
    intervals: list[dict[str, Any]] = []

    grouped_rows: dict[int, list[dict[str, Any]]] = {}
    for row in diff_rows:
        grouped_rows.setdefault(row["subseriesIndex"], []).append(row)

    for subseries_index in sorted(grouped_rows):
        rows = grouped_rows[subseries_index]
        previous_nonzero: dict[str, Any] | None = None
        for row in rows:
            current_sign = _sign(row["signedDiff"])
            if current_sign == 0:
                continue
            if previous_nonzero is not None and _sign(previous_nonzero["signedDiff"]) != current_sign:
                event_extremum = extrema[row["endOrdinal"] - 1]
                event = {
                    "localIndex": event_extremum.local_index,
                    "globalIndex": event_extremum.global_index,
                    "extremumOrdinal": event_extremum.ordinal,
                    "amplitude": event_extremum.value,
                    "signedDiff": row["signedDiff"],
                    "absDiff": abs(row["signedDiff"]),
                    "subseriesIndex": subseries_index,
                }
                sign_changes.append(event)
            previous_nonzero = row

    sign_changes.sort(key=lambda row: (row["localIndex"], row["extremumOrdinal"]))

    grouped_sign_changes: dict[int, list[dict[str, Any]]] = {}
    for row in sign_changes:
        grouped_sign_changes.setdefault(row["subseriesIndex"], []).append(row)

    for subseries_index in sorted(grouped_sign_changes):
        rows = grouped_sign_changes[subseries_index]
        for left, right in zip(rows, rows[1:]):
            signed_amplitude_diff = right["amplitude"] - left["amplitude"]
            sign_change_diff_rows.append(
                {
                    "startLocalIndex": left["localIndex"],
                    "endLocalIndex": right["localIndex"],
                    "startGlobalIndex": left["globalIndex"],
                    "endGlobalIndex": right["globalIndex"],
                    "startOrdinal": left["extremumOrdinal"],
                    "endOrdinal": right["extremumOrdinal"],
                    "startAmplitude": left["amplitude"],
                    "endAmplitude": right["amplitude"],
                    "signedAmplitudeDiff": signed_amplitude_diff,
                    "absAmplitudeDiff": abs(signed_amplitude_diff),
                    "startSubseriesIndex": left["subseriesIndex"],
                    "endSubseriesIndex": right["subseriesIndex"],
                }
            )
            intervals.append(
                {
                    "startLocalIndex": left["localIndex"],
                    "endLocalIndex": right["localIndex"],
                    "startGlobalIndex": left["globalIndex"],
                    "endGlobalIndex": right["globalIndex"],
                    "duration": right["localIndex"] - left["localIndex"],
                    "absAmplitudeDiff": abs(signed_amplitude_diff),
                    "startAmplitude": left["amplitude"],
                    "endAmplitude": right["amplitude"],
                    "startSubseriesIndex": left["subseriesIndex"],
                    "endSubseriesIndex": right["subseriesIndex"],
                }
            )

    sign_change_diff_rows.sort(
        key=lambda row: (row["endLocalIndex"], row["startLocalIndex"], row["endSubseriesIndex"], row["startSubseriesIndex"])
    )
    intervals.sort(
        key=lambda row: (row["startSubseriesIndex"], row["startLocalIndex"], row["endLocalIndex"])
    )

    return diff_rows, sign_changes, sign_change_diff_rows, intervals


def build_k_analyses(extrema: list[Extremum], max_k_raw: str | None) -> tuple[list[dict[str, Any]], int]:
    if len(extrema) < 2:
        return [], -1

    max_possible_k = _max_k_for_extrema(len(extrema))
    requested = _as_nonnegative_int(max_k_raw, "M")
    effective_max_k = max_possible_k if requested is None else min(max_possible_k, requested)

    analyses: list[dict[str, Any]] = []
    for k in range(0, effective_max_k + 1):
        step = 2**k
        diff_rows, sign_changes, sign_change_diff_rows, intervals = _event_rows_for_k(extrema, step)
        analyses.append(
            {
                "k": k,
                "step": step,
                "diffRows": diff_rows,
                "signChanges": sign_changes,
                "signChangeDiffRows": sign_change_diff_rows,
                "intervals": intervals,
            }
        )
    return analyses, effective_max_k


def group_intervals(all_intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not all_intervals:
        return []

    rows = sorted(all_intervals, key=lambda item: item["duration"])
    tolerance = rows[0]["duration"] / 2.0
    groups: list[dict[str, Any]] = []
    idx = 0

    while idx < len(rows):
        anchor = rows[idx]["duration"]
        group_rows = [rows[idx]]
        idx += 1
        while idx < len(rows) and rows[idx]["duration"] - anchor <= tolerance:
            group_rows.append(rows[idx])
            idx += 1

        durations = [row["duration"] for row in group_rows]
        amplitude_moduli = [row["absAmplitudeDiff"] for row in group_rows]
        groups.append(
            {
                "groupIndex": len(groups) + 1,
                "avgDuration": sum(durations) / len(durations),
                "avgAmplitude": sum(amplitude_moduli) / (2 * len(amplitude_moduli)),
                "avgFrequency": 1.0 / (2.0 * (sum(durations) / len(durations))),
                "count": len(group_rows),
                "minDuration": min(durations),
                "maxDuration": max(durations),
                "rows": group_rows,
            }
        )

    return groups


def _sample_rows(samples: list[Sample]) -> list[dict[str, Any]]:
    return [
        {"globalIndex": sample.global_index, "localIndex": sample.local_index, "value": sample.value}
        for sample in samples
    ]


def _extrema_rows(extrema: list[Extremum]) -> list[dict[str, Any]]:
    return [
        {
            "ordinal": item.ordinal,
            "globalIndex": item.global_index,
            "localIndex": item.local_index,
            "value": item.value,
            "kind": item.kind,
        }
        for item in extrema
    ]


def analyze_text(
    text: str,
    *,
    frame_size: str | None,
    frame_number: str | None,
    manual_start: str | None,
    manual_end: str | None,
    max_k: str | None,
    filename: str | None = None,
) -> dict[str, Any]:
    source_points = parse_input_text(text)
    frame_samples, frame_info = select_frame(
        source_points,
        frame_size_raw=frame_size,
        frame_number_raw=frame_number,
        manual_start_raw=manual_start,
        manual_end_raw=manual_end,
    )
    extrema = extract_extrema(frame_samples)
    k_analyses, effective_max_k = build_k_analyses(extrema, max_k)

    all_intervals: list[dict[str, Any]] = []
    for analysis in k_analyses:
        for row in analysis["intervals"]:
            row_with_k = dict(row)
            row_with_k["k"] = analysis["k"]
            all_intervals.append(row_with_k)

    grouped = group_intervals(all_intervals)

    return {
        "filename": filename or "uploaded.txt",
        "frameInfo": frame_info,
        "sourceCount": len(source_points),
        "frameRows": _sample_rows(frame_samples),
        "extrema": _extrema_rows(extrema),
        "kAnalyses": k_analyses,
        "effectiveMaxK": effective_max_k,
        "aggregateGroups": grouped,
        "spectrumGroups": grouped,
    }
