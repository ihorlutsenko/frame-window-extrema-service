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


@dataclass(frozen=True)
class SequenceRun:
    value: float
    point: Extremum


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


def _build_sequence_runs(points: list[Extremum]) -> list[SequenceRun]:
    runs: list[SequenceRun] = []
    start = 0
    while start < len(points):
        end = start + 1
        while end < len(points) and points[end].value == points[start].value:
            end += 1

        run_length = end - start
        representative_offset = (run_length - 1) // 2
        runs.append(SequenceRun(value=points[start].value, point=points[start + representative_offset]))
        start = end

    return runs


def extract_extrema_from_sequence(points: list[Extremum]) -> list[Extremum]:
    if len(points) < 3:
        return []

    runs = _build_sequence_runs(points)
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

        base = current_run.point
        extrema.append(
            Extremum(
                ordinal=ordinal,
                global_index=base.global_index,
                local_index=base.local_index,
                value=base.value,
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


def _article_rows_for_sequence(
    points: list[Extremum],
    *,
    branch_label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diff_rows: list[dict[str, Any]] = []
    sign_changes: list[dict[str, Any]] = []
    sign_change_diff_rows: list[dict[str, Any]] = []
    intervals: list[dict[str, Any]] = []

    if len(points) < 2:
        return diff_rows, sign_changes, sign_change_diff_rows, intervals

    previous_sign = None
    for current, shifted in zip(points, points[1:]):
        signed_diff = shifted.value - current.value
        row = {
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
            "subseriesIndex": branch_label,
        }
        diff_rows.append(row)
        sign = _sign(signed_diff)
        if sign != 0 and previous_sign is not None and sign != previous_sign:
            sign_changes.append(
                {
                    "localIndex": shifted.local_index,
                    "globalIndex": shifted.global_index,
                    "extremumOrdinal": shifted.ordinal,
                    "displayKey": f"{branch_label}:{shifted.ordinal}",
                    "amplitude": shifted.value,
                    "signedDiff": signed_diff,
                    "absDiff": abs(signed_diff),
                    "subseriesIndex": branch_label,
                }
            )
        if sign != 0:
            previous_sign = sign

        sign_change_diff_rows.append(
            {
                "startLocalIndex": current.local_index,
                "endLocalIndex": shifted.local_index,
                "startGlobalIndex": current.global_index,
                "endGlobalIndex": shifted.global_index,
                "startOrdinal": current.ordinal,
                "endOrdinal": shifted.ordinal,
                "startAmplitude": current.value,
                "endAmplitude": shifted.value,
                "signedAmplitudeDiff": signed_diff,
                "absAmplitudeDiff": abs(signed_diff),
                "startSubseriesIndex": branch_label,
                "endSubseriesIndex": branch_label,
            }
        )
        intervals.append(
            {
                "startLocalIndex": current.local_index,
                "endLocalIndex": shifted.local_index,
                "startGlobalIndex": current.global_index,
                "endGlobalIndex": shifted.global_index,
                "duration": shifted.local_index - current.local_index,
                "absAmplitudeDiff": abs(signed_diff),
                "startAmplitude": current.value,
                "endAmplitude": shifted.value,
                "startSubseriesIndex": branch_label,
                "endSubseriesIndex": branch_label,
            }
        )

    return diff_rows, sign_changes, sign_change_diff_rows, intervals


def build_article_analyses(extrema: list[Extremum], max_k_raw: str | None) -> tuple[list[dict[str, Any]], int]:
    if len(extrema) < 2:
        return [], -1

    requested = _as_nonnegative_int(max_k_raw, "M")
    analyses: list[dict[str, Any]] = []
    current_sequences: list[tuple[str, list[Extremum]]] = [("base", extrema)]
    level = 0

    while current_sequences and (requested is None or level <= requested):
        diff_rows: list[dict[str, Any]] = []
        sign_changes: list[dict[str, Any]] = []
        sign_change_diff_rows: list[dict[str, Any]] = []
        intervals: list[dict[str, Any]] = []
        display_extrema: list[dict[str, Any]] = []

        for branch_label, sequence in current_sequences:
            local_diff_rows, local_sign_changes, local_sign_change_diff_rows, local_intervals = _article_rows_for_sequence(
                sequence,
                branch_label=branch_label,
            )
            diff_rows.extend(local_diff_rows)
            sign_changes.extend(local_sign_changes)
            sign_change_diff_rows.extend(local_sign_change_diff_rows)
            intervals.extend(local_intervals)
            display_extrema.extend(
                {
                    "ordinal": item.ordinal,
                    "displayKey": f"{branch_label}:{item.ordinal}",
                    "displayLabel": f"{branch_label}.{item.ordinal}",
                    "globalIndex": item.global_index,
                    "localIndex": item.local_index,
                    "value": item.value,
                    "kind": item.kind,
                    "branch": branch_label,
                }
                for item in sequence
            )

        analyses.append(
            {
                "k": level,
                "step": 2**level,
                "diffRows": sorted(diff_rows, key=lambda row: (row["endLocalIndex"], row["startLocalIndex"])),
                "signChanges": sorted(sign_changes, key=lambda row: (row["localIndex"], row["extremumOrdinal"])),
                "signChangeDiffRows": sorted(
                    sign_change_diff_rows,
                    key=lambda row: (row["endLocalIndex"], row["startLocalIndex"]),
                ),
                "intervals": sorted(intervals, key=lambda row: (row["startLocalIndex"], row["endLocalIndex"])),
                "displayExtrema": sorted(display_extrema, key=lambda row: (row["localIndex"], row["ordinal"], row["branch"])),
            }
        )

        next_sequences: list[tuple[str, list[Extremum]]] = []
        for branch_label, sequence in current_sequences:
            for filter_kind in ("max", "min"):
                filtered = [item for item in sequence if item.kind == filter_kind]
                reduced = extract_extrema_from_sequence(filtered)
                if len(reduced) >= 2:
                    next_sequences.append((f"{branch_label}:{filter_kind}", reduced))

        current_sequences = next_sequences
        level += 1

    return analyses, len(analyses) - 1


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


def build_patent_spectrum_groups(k_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_rows: dict[tuple[int, Any], list[dict[str, Any]]] = {}
    for analysis in k_analyses:
        for row in analysis["intervals"]:
            branch = row["startSubseriesIndex"]
            grouped_rows.setdefault((analysis["k"], branch), []).append(dict(row))

    spectrum_groups: list[dict[str, Any]] = []
    for (k, branch), rows in sorted(grouped_rows.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        local_groups = group_intervals(rows)
        for group in local_groups:
            enriched = dict(group)
            enriched["k"] = k
            enriched["branch"] = branch
            spectrum_groups.append(enriched)

    for index, group in enumerate(spectrum_groups, start=1):
        group["groupIndex"] = index

    return spectrum_groups


def build_article_spectrum_groups(k_analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for analysis in k_analyses:
        intervals = analysis["intervals"]
        if not intervals:
            continue

        durations = [row["duration"] for row in intervals]
        amplitude_moduli = [row["absAmplitudeDiff"] for row in intervals]
        avg_duration = sum(durations) / len(durations)
        avg_amplitude = sum(amplitude_moduli) / (2 * len(amplitude_moduli))
        groups.append(
            {
                "groupIndex": len(groups) + 1,
                "k": analysis["k"],
                "avgDuration": avg_duration,
                "avgAmplitude": avg_amplitude,
                "avgFrequency": 1.0 / (2.0 * avg_duration),
                "count": len(intervals),
                "minDuration": min(durations),
                "maxDuration": max(durations),
                "rows": intervals,
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
    mode: str = "patent",
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
    if mode == "article":
        k_analyses, effective_max_k = build_article_analyses(extrema, max_k)
        mode_name = "Статейна логіка"
    else:
        k_analyses, effective_max_k = build_k_analyses(extrema, max_k)
        mode_name = "Патентна логіка"

    all_intervals: list[dict[str, Any]] = []
    for analysis in k_analyses:
        for row in analysis["intervals"]:
            row_with_k = dict(row)
            row_with_k["k"] = analysis["k"]
            all_intervals.append(row_with_k)

    grouped = group_intervals(all_intervals)
    if mode == "article":
        spectrum_groups = build_article_spectrum_groups(k_analyses)
    else:
        spectrum_groups = build_patent_spectrum_groups(k_analyses)

    return {
        "mode": mode,
        "modeName": mode_name,
        "filename": filename or "uploaded.txt",
        "frameInfo": frame_info,
        "sourceCount": len(source_points),
        "frameRows": _sample_rows(frame_samples),
        "extrema": _extrema_rows(extrema),
        "kAnalyses": k_analyses,
        "effectiveMaxK": effective_max_k,
        "aggregateGroups": grouped,
        "spectrumGroups": spectrum_groups,
    }
