from __future__ import annotations

import unittest

from frame_window_service.analysis import (
    Extremum,
    build_article_analyses,
    build_patent_crossk_spectrum_groups,
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

    def test_article_mode_builds_recursive_levels(self) -> None:
        amplitudes = [10, 0, 10, -10, 0, -10, 10, 0, 10, -10, 0, -10]
        extrema = [
            Extremum(
                ordinal=index,
                global_index=index * 10,
                local_index=index * 10,
                value=value,
                kind="max" if index % 2 else "min",
            )
            for index, value in enumerate(amplitudes, start=1)
        ]

        analyses, effective_max_k = build_article_analyses(extrema, None)
        self.assertGreaterEqual(effective_max_k, 1)
        self.assertEqual(analyses[0]["k"], 0)
        self.assertEqual(analyses[1]["k"], 1)
        self.assertTrue(analyses[1]["intervals"])

    def test_article_mode_finds_both_166_and_1000_scales_for_sin3x_plus_sinx(self) -> None:
        import math

        values = []
        for sample_index in range(5000):
            x = 2 * math.pi * sample_index / 1000
            values.append(f"{math.sin(3 * x) + math.sin(x):.5f}")

        result = analyze_text(
            "\n".join(values),
            mode="article",
            frame_size="5000",
            frame_number="1",
            manual_start=None,
            manual_end=None,
            max_k=None,
        )

        raw_avg_durations = sorted(round(group["avgDuration"], 2) for group in result["aggregateGroups"])
        self.assertTrue(any(abs(value - 348.0) < 0.1 for value in raw_avg_durations))
        self.assertTrue(any(abs(value - 652.0) < 0.1 for value in raw_avg_durations))

        spectrum_avg_durations = sorted(round(group["avgDuration"], 2) for group in result["spectrumGroups"])
        self.assertTrue(any(abs(value - 166.67) < 1.5 for value in spectrum_avg_durations))
        self.assertTrue(any(abs(value - 500.0) < 0.3 for value in spectrum_avg_durations))

    def test_patent_crossk_merges_equal_durations_from_different_k(self) -> None:
        groups = build_patent_crossk_spectrum_groups(
            [
                {
                    "k": 0,
                    "intervals": [
                        {"duration": 10, "absAmplitudeDiff": 4, "startSubseriesIndex": 1},
                        {"duration": 12, "absAmplitudeDiff": 8, "startSubseriesIndex": 1},
                    ],
                },
                {
                    "k": 2,
                    "intervals": [
                        {"duration": 10, "absAmplitudeDiff": 6, "startSubseriesIndex": 3},
                    ],
                },
            ]
        )
        self.assertEqual([group["avgDuration"] for group in groups], [10.0, 12.0])
        self.assertAlmostEqual(groups[0]["avgAmplitude"], (4 + 6) / 4)
        self.assertAlmostEqual(groups[0]["avgFrequency"], 1 / 20)
        self.assertEqual(groups[0]["count"], 2)


if __name__ == "__main__":
    unittest.main()
