from __future__ import annotations

import unittest

from frame_window_service.analysis import (
    Extremum,
    extract_extrema,
    group_intervals,
    parse_input_text,
    select_frame,
    analyze_text,
    build_k_analyses,
)


class FrameWindowAnalysisTests(unittest.TestCase):
    def test_parse_input_one_number_per_line(self) -> None:
        points = parse_input_text("1\n2\n3\n")
        self.assertEqual(points, [(1, 1.0), (2, 2.0), (3, 3.0)])

    def test_parse_csv_style_lines(self) -> None:
        points = parse_input_text("1.5,2.5,3.5\n4.5,5.5\n")
        self.assertEqual(
            points,
            [(1, 1.5), (2, 2.5), (3, 3.5), (4, 4.5), (5, 5.5)],
        )

    def test_parse_semicolon_csv_with_decimal_comma(self) -> None:
        points = parse_input_text("1,5;2,5;3,5\n")
        self.assertEqual(points, [(1, 1.5), (2, 2.5), (3, 3.5)])

    def test_manual_range_has_priority(self) -> None:
        points = parse_input_text("1\n2\n3\n4\n5\n6\n")
        samples, meta = select_frame(points, "2", "3", "2", "4")
        self.assertEqual(meta["type"], "manual")
        self.assertEqual([item.global_index for item in samples], [2, 3, 4])

    def test_plateau_middle_choice_matches_previous_rule(self) -> None:
        samples, _ = select_frame(parse_input_text("1\n3\n3\n3\n1\n"), "5", "1", None, None)
        extrema = extract_extrema(samples)
        self.assertEqual(len(extrema), 1)
        self.assertEqual(extrema[0].local_index, 3)

    def test_k_and_grouping_pipeline(self) -> None:
        result = analyze_text(
            "1\n5\n2\n4\n1\n6\n2\n",
            frame_size="7",
            frame_number="1",
            manual_start=None,
            manual_end=None,
            max_k=None,
        )
        self.assertEqual(len(result["extrema"]), 5)
        self.assertEqual(result["effectiveMaxK"], 2)
        k0 = result["kAnalyses"][0]
        self.assertEqual(len(k0["signChanges"]), 3)
        self.assertEqual(len(k0["intervals"]), 2)
        self.assertEqual(result["aggregateGroups"][0]["avgDuration"], 1.0)
        self.assertAlmostEqual(result["aggregateGroups"][0]["avgAmplitude"], 2.0)

    def test_grouping_uses_global_minimum_half_tolerance(self) -> None:
        groups = group_intervals(
            [
                {"duration": 2, "absAmplitudeDiff": 4},
                {"duration": 2, "absAmplitudeDiff": 6},
                {"duration": 3, "absAmplitudeDiff": 8},
                {"duration": 6, "absAmplitudeDiff": 10},
            ]
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["count"], 3)
        self.assertAlmostEqual(groups[0]["avgDuration"], 7 / 3)
        self.assertAlmostEqual(groups[0]["avgAmplitude"], (4 + 6 + 8) / 6)
        self.assertAlmostEqual(groups[0]["avgFrequency"], 3 / 14)

    def test_requested_zero_means_only_k_zero(self) -> None:
        result = analyze_text(
            "1\n5\n2\n4\n1\n6\n2\n",
            frame_size="7",
            frame_number="1",
            manual_start=None,
            manual_end=None,
            max_k="0",
        )
        self.assertEqual(result["effectiveMaxK"], 0)
        self.assertEqual([row["k"] for row in result["kAnalyses"]], [0])

    def test_k1_sign_changes_and_intervals_stay_within_each_subseries(self) -> None:
        amplitudes = [10, 50, 20, 60, 30, 40, 15, 70, 25]
        extrema = [
            Extremum(
                ordinal=index,
                global_index=index,
                local_index=index,
                value=value,
                kind="max" if index % 2 else "min",
            )
            for index, value in enumerate(amplitudes, start=1)
        ]

        analyses, _ = build_k_analyses(extrema, "1")
        k1 = analyses[1]

        self.assertEqual(
            [row["extremumOrdinal"] for row in k1["signChanges"]],
            [6, 7, 8, 9],
        )
        self.assertEqual(
            sorted((row["startLocalIndex"], row["endLocalIndex"]) for row in k1["intervals"]),
            [(6, 8), (7, 9)],
        )
        self.assertEqual(
            sorted(
                (row["startOrdinal"], row["endOrdinal"], row["signedAmplitudeDiff"], row["absAmplitudeDiff"])
                for row in k1["signChangeDiffRows"]
            ),
            [
                (6, 8, 30, 30),
                (7, 9, 10, 10),
            ],
        )

    def test_analyze_text_exposes_frequency_for_groups(self) -> None:
        result = analyze_text(
            "1\n5\n2\n4\n1\n6\n2\n",
            frame_size="7",
            frame_number="1",
            manual_start=None,
            manual_end=None,
            max_k=None,
        )
        self.assertIn("spectrumGroups", result)
        self.assertAlmostEqual(
            result["aggregateGroups"][0]["avgFrequency"],
            1 / (2 * result["aggregateGroups"][0]["avgDuration"]),
        )


if __name__ == "__main__":
    unittest.main()
