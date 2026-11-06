"""Unit tests for schedulers.py.

Run:
    python3 -m unittest -v test_schedulers
"""

import math
import unittest

from schedulers import (
    Candidate,
    POLICY_NAMES,
    Scheduler,
    SchedulerConfig,
)


def packet(
    packet_id,
    station=0,
    kind="bg",
    arrival=0.0,
    nominal=0.001,
    deadline=None,
):
    return Candidate(
        packet_id=packet_id,
        station=station,
        traffic_class=kind,
        arrival_s=arrival,
        nominal_service_s=nominal,
        deadline_s=deadline,
    )


class CandidateValidationTests(unittest.TestCase):
    def test_valid_background_packet(self):
        candidate = packet(0)
        self.assertEqual(candidate.traffic_class, "bg")
        self.assertIsNone(candidate.deadline_s)

    def test_valid_real_time_packet(self):
        candidate = packet(
            0,
            kind="rt",
            deadline=0.020,
        )
        self.assertEqual(candidate.deadline_s, 0.020)

    def test_invalid_candidates(self):
        invalid_arguments = [
            {"packet_id": -1},
            {"packet_id": 0, "station": -1},
            {"packet_id": 0, "kind": "unknown"},
            {"packet_id": 0, "arrival": -1.0},
            {"packet_id": 0, "arrival": math.nan},
            {"packet_id": 0, "nominal": 0.0},
            {"packet_id": 0, "nominal": math.inf},
            {"packet_id": 0, "kind": "rt"},
            {
                "packet_id": 0,
                "kind": "rt",
                "arrival": 0.010,
                "deadline": 0.010,
            },
            {
                "packet_id": 0,
                "kind": "bg",
                "deadline": 0.020,
            },
        ]

        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    packet(**arguments)

    def test_invalid_configurations(self):
        invalid_arguments = [
            {"stations": 0},
            {"quantum_s": 0.0},
            {"credit_cap_s": -0.001},
            {"urgency_horizon_s": 0.0},
            {"fairness_weight": -0.1},
            {"background_share": 1.1},
            {"background_debt_cap_s": 0.0},
            {"estimator_alpha": 0.0},
            {"estimator_alpha": 1.1},
        ]

        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    SchedulerConfig(**arguments)


class SchedulingContractTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler(
            "proposed",
            SchedulerConfig(stations=2),
        )

    def test_empty_queues_return_none(self):
        self.assertIsNone(self.scheduler.choose(0.0, []))

    def test_choose_requires_previous_completion(self):
        selected = self.scheduler.choose(0.0, [packet(0)])

        with self.assertRaises(RuntimeError):
            self.scheduler.choose(0.0, [packet(1)])

        self.scheduler.complete(selected.packet_id, 0.001)

    def test_complete_requires_pending_packet(self):
        with self.assertRaises(RuntimeError):
            self.scheduler.complete(0, 0.001)

    def test_wrong_completion_id_preserves_pending_packet(self):
        self.scheduler.choose(0.0, [packet(7)])

        with self.assertRaises(ValueError):
            self.scheduler.complete(8, 0.001)

        self.assertEqual(
            self.scheduler.diagnostics()["pending_packet_id"],
            7,
        )

        self.scheduler.complete(7, 0.001)

    def test_invalid_service_durations(self):
        self.scheduler.choose(0.0, [packet(0)])

        for duration in [0.0, -0.001, math.nan, math.inf]:
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    self.scheduler.complete(0, duration)

        # Invalid attempts do not discard the pending transmission.
        self.scheduler.complete(0, 0.001)

    def test_cannot_schedule_before_completion_time(self):
        self.scheduler.choose(0.0, [packet(0)])
        self.scheduler.complete(0, 0.002)

        with self.assertRaises(ValueError):
            self.scheduler.choose(0.001, [])

        self.assertIsNone(self.scheduler.choose(0.002, []))

    def test_future_arrival_is_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.choose(
                0.0,
                [packet(0, arrival=0.001)],
            )

    def test_expired_packet_is_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.choose(
                0.010,
                [packet(0, kind="rt", deadline=0.010)],
            )

    def test_duplicate_packet_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.choose(
                0.0,
                [packet(0, station=0), packet(0, station=1)],
            )

    def test_multiple_heads_from_same_queue_are_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.choose(
                0.0,
                [packet(0), packet(1)],
            )

    def test_unconfigured_station_is_rejected(self):
        with self.assertRaises(ValueError):
            self.scheduler.choose(
                0.0,
                [packet(0, station=2)],
            )


class BaselineTests(unittest.TestCase):
    def test_round_robin_rotates_between_stations(self):
        scheduler = Scheduler(
            "round_robin",
            SchedulerConfig(stations=2),
        )

        first = scheduler.choose(
            0.0,
            [packet(0, station=0), packet(1, station=1)],
        )
        self.assertEqual(first.station, 0)
        scheduler.complete(first.packet_id, 0.001)

        second = scheduler.choose(
            0.001,
            [packet(2, station=0), packet(1, station=1)],
        )
        self.assertEqual(second.station, 1)

    def test_round_robin_skips_empty_stations(self):
        scheduler = Scheduler(
            "round_robin",
            SchedulerConfig(stations=4),
        )

        selected = scheduler.choose(
            0.0,
            [packet(0, station=3)],
        )
        self.assertEqual(selected.station, 3)

    def test_edf_selects_earliest_deadline(self):
        scheduler = Scheduler(
            "edf",
            SchedulerConfig(stations=2),
        )

        selected = scheduler.choose(
            0.0,
            [
                packet(0, station=0, kind="rt", deadline=0.030),
                packet(1, station=1, kind="rt", deadline=0.010),
                packet(2, station=0, kind="bg"),
            ],
        )
        self.assertEqual(selected.packet_id, 1)

    def test_edf_background_fallback_is_fifo(self):
        scheduler = Scheduler(
            "edf",
            SchedulerConfig(stations=2),
        )

        selected = scheduler.choose(
            0.002,
            [
                packet(0, station=0, arrival=0.001),
                packet(1, station=1, arrival=0.0),
            ],
        )
        self.assertEqual(selected.packet_id, 1)

    def test_drr_can_serve_multiple_packets_in_one_visit(self):
        scheduler = Scheduler(
            "service_drr",
            SchedulerConfig(stations=2, quantum_s=0.001),
        )

        first = scheduler.choose(
            0.0,
            [
                packet(0, station=0, nominal=0.0004),
                packet(1, station=1, nominal=0.0004),
            ],
        )
        self.assertEqual(first.station, 0)
        scheduler.complete(first.packet_id, 0.0004)

        second = scheduler.choose(
            0.0004,
            [
                packet(2, station=0, nominal=0.0004),
                packet(1, station=1, nominal=0.0004),
            ],
        )
        self.assertEqual(second.station, 0)
        scheduler.complete(second.packet_id, 0.0004)

        third = scheduler.choose(
            0.0008,
            [
                packet(3, station=0, nominal=0.0004),
                packet(1, station=1, nominal=0.0004),
            ],
        )
        self.assertEqual(third.station, 1)

    def test_drr_charges_actual_not_predicted_service(self):
        scheduler = Scheduler(
            "service_drr",
            SchedulerConfig(stations=2, quantum_s=0.001),
        )

        scheduler.choose(0.0, [packet(0)])
        scheduler.complete(0, 0.003)

        self.assertAlmostEqual(
            scheduler.diagnostics()["drr_credit_s"][0],
            -0.002,
        )


class ProposedAndAblationTests(unittest.TestCase):
    def test_urgency_ablation_changes_selection(self):
        candidates = [
            packet(0, station=0, kind="bg"),
            packet(1, station=1, kind="rt", deadline=0.004),
        ]
        config = SchedulerConfig(stations=2)

        proposed = Scheduler("proposed", config)
        no_urgency = Scheduler("no_urgency", config)

        self.assertEqual(
            proposed.choose(0.0, candidates).packet_id,
            1,
        )
        self.assertEqual(
            no_urgency.choose(0.0, candidates).packet_id,
            0,
        )

    def test_fairness_ablation_changes_selection(self):
        config = SchedulerConfig(stations=2)
        proposed = Scheduler("proposed", config)
        no_fairness = Scheduler("no_fairness", config)

        for scheduler in (proposed, no_fairness):
            selected = scheduler.choose(
                0.0,
                [
                    packet(0, station=0),
                    packet(1, station=1),
                ],
            )
            self.assertEqual(selected.station, 0)
            scheduler.complete(selected.packet_id, 0.001)

        next_candidates = [
            packet(2, station=0, arrival=0.0),
            packet(3, station=1, arrival=0.0002),
        ]

        # Station 1 has positive service credit.
        self.assertEqual(
            proposed.choose(0.001, next_candidates).station,
            1,
        )

        # Without credit-based fairness, FIFO selects station 0.
        self.assertEqual(
            no_fairness.choose(0.001, next_candidates).station,
            0,
        )

    def test_retry_estimation_ablation_changes_feasibility(self):
        config = SchedulerConfig(
            stations=2,
            estimator_alpha=0.5,
        )
        proposed = Scheduler("proposed", config)
        no_retry = Scheduler("no_retry_estimate", config)

        training = packet(
            100,
            station=1,
            kind="rt",
            nominal=0.001,
            deadline=0.020,
        )

        for scheduler in (proposed, no_retry):
            scheduler.choose(0.0, [training])
            scheduler.complete(100, 0.003)

        candidates = [
            packet(
                2,
                station=0,
                kind="bg",
                arrival=0.003,
            ),
            packet(
                3,
                station=1,
                kind="rt",
                arrival=0.003,
                nominal=0.001,
                deadline=0.0045,
            ),
        ]

        self.assertAlmostEqual(
            proposed.estimate(candidates[1]),
            0.002,
        )
        self.assertAlmostEqual(
            no_retry.estimate(candidates[1]),
            0.001,
        )

        # Learned estimate predicts insufficient slack, so fallback wins.
        self.assertEqual(
            proposed.choose(0.003, candidates).packet_id,
            2,
        )

        # Nominal-only estimate predicts feasible urgent service.
        self.assertEqual(
            no_retry.choose(0.003, candidates).packet_id,
            3,
        )

    def test_background_debt_eventually_triggers_reservation(self):
        scheduler = Scheduler(
            "proposed",
            SchedulerConfig(
                stations=2,
                background_share=0.5,
            ),
        )

        background = packet(100, station=1)

        for step in range(2):
            now = step * 0.001

            urgent = packet(
                step,
                station=0,
                kind="rt",
                arrival=now,
                deadline=now + 0.003,
            )

            selected = scheduler.choose(
                now,
                [urgent, background],
            )
            self.assertEqual(selected.traffic_class, "rt")
            scheduler.complete(selected.packet_id, 0.001)

        self.assertAlmostEqual(
            scheduler.diagnostics()["background_debt_s"],
            0.001,
        )

        selected = scheduler.choose(
            0.002,
            [
                packet(
                    2,
                    station=0,
                    kind="rt",
                    arrival=0.002,
                    deadline=0.005,
                ),
                background,
            ],
        )

        self.assertEqual(selected.packet_id, 100)
        scheduler.complete(selected.packet_id, 0.001)

        self.assertAlmostEqual(
            scheduler.diagnostics()["background_debt_s"],
            0.0005,
        )

    def test_credit_and_background_debt_caps(self):
        scheduler = Scheduler(
            "proposed",
            SchedulerConfig(
                stations=2,
                credit_cap_s=0.002,
                background_share=0.5,
                background_debt_cap_s=0.003,
            ),
        )

        selected = scheduler.choose(
            0.0,
            [
                packet(0, station=0, kind="rt", deadline=1.0),
                packet(1, station=1, kind="bg"),
            ],
        )
        self.assertEqual(selected.packet_id, 0)
        scheduler.complete(selected.packet_id, 0.1)

        state = scheduler.diagnostics()

        self.assertAlmostEqual(
            state["station_credit_s"][1],
            0.002,
        )
        self.assertAlmostEqual(
            state["background_debt_s"],
            0.003,
        )

        scheduler.choose(0.1, [])

        state = scheduler.diagnostics()
        self.assertEqual(state["station_credit_s"], [0.0, 0.0])
        self.assertEqual(state["background_debt_s"], 0.0)

    def test_estimates_are_separate_by_station_and_class(self):
        scheduler = Scheduler(
            "proposed",
            SchedulerConfig(
                stations=2,
                estimator_alpha=0.5,
            ),
        )

        training = packet(
            0,
            station=0,
            kind="rt",
            deadline=0.020,
        )

        scheduler.choose(0.0, [training])
        scheduler.complete(0, 0.003)

        self.assertAlmostEqual(scheduler.estimate(training), 0.002)

        self.assertAlmostEqual(
            scheduler.estimate(packet(1, station=0, kind="bg")),
            0.001,
        )

        self.assertAlmostEqual(
            scheduler.estimate(
                packet(2, station=1, kind="rt", deadline=0.020)
            ),
            0.001,
        )


class ReproducibilityTests(unittest.TestCase):
    @staticmethod
    def selection_sequence(policy):
        scheduler = Scheduler(
            policy,
            SchedulerConfig(stations=3),
        )

        sequence = []
        now = 0.0

        for step in range(12):
            candidates = []

            for station in range(3):
                candidates.extend([
                    packet(
                        100 * step + 2 * station,
                        station=station,
                        kind="bg",
                        arrival=now,
                    ),
                    packet(
                        100 * step + 2 * station + 1,
                        station=station,
                        kind="rt",
                        arrival=now,
                        deadline=now + 0.004,
                    ),
                ])

            selected = scheduler.choose(now, candidates)
            sequence.append(selected.packet_id)

            service = 0.001 + 0.0001 * selected.station
            scheduler.complete(selected.packet_id, service)
            now += service

        return sequence

    def test_every_policy_is_deterministic_for_identical_inputs(self):
        for policy in POLICY_NAMES:
            with self.subTest(policy=policy):
                self.assertEqual(
                    self.selection_sequence(policy),
                    self.selection_sequence(policy),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
